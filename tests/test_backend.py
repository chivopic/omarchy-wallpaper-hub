import unittest
import unittest.mock
import os
import sys
import json
import tempfile
import struct
from pathlib import Path
import subprocess
import multiprocessing
from contextlib import redirect_stdout
from io import StringIO

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend import (
    ImageValidator,
    MetadataStore,
    WallpaperCatalog,
    WallpaperController,
    ImportManager,
    FileManager,
    MAX_FILE_SIZE,
    MAX_PIXELS
)


def _concurrent_metadata_writer(metadata_file, worker_id, start_barrier):
    import backend
    backend.Paths.metadata_file = staticmethod(lambda: Path(metadata_file))
    store = MetadataStore()
    start_barrier.wait(timeout=10)
    store.set_favorite(f"worker:{worker_id}", True)
    store.update_item(f"worker:{worker_id}", {"id": f"worker:{worker_id}"})


class TestImageValidator(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def create_fake_png(self, width=1920, height=1080) -> Path:
        p = self.d / "test.png"
        header = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", width, height) + b"\x08\x06\x00\x00\x00"
        p.write_bytes(header + b"\x00" * 100)
        return p

    def create_fake_jpeg(self, width=1920, height=1080) -> Path:
        p = self.d / "test.jpg"
        data = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00"
            b"\xff\xc0\x00\x11\x08" + struct.pack(">HH", height, width) + b"\x03\x01\x11\x00\x02\x11\x01\x03\x11\x01"
            b"\xff\xd9"
        )
        p.write_bytes(data)
        return p

    def create_fake_gif(self) -> Path:
        p = self.d / "test.gif"
        p.write_bytes(b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
        return p

    def test_valid_png(self):
        p = self.create_fake_png(800, 600)
        fmt, w, h, size = ImageValidator.parse_header(p)
        self.assertEqual(fmt, "png")
        self.assertEqual(w, 800)
        self.assertEqual(h, 600)

    def test_valid_jpeg(self):
        p = self.create_fake_jpeg(1024, 768)
        fmt, w, h, size = ImageValidator.parse_header(p)
        self.assertEqual(fmt, "jpeg")
        self.assertEqual(w, 1024)
        self.assertEqual(h, 768)

    def test_reject_gif(self):
        p = self.create_fake_gif()
        with self.assertRaises(ValueError) as ctx:
            ImageValidator.parse_header(p)
        self.assertIn("GIF files are not supported", str(ctx.exception))

    def test_reject_oversized_resolution(self):
        # 10000 x 6000 = 60 MP > 50 MP
        p = self.create_fake_png(10000, 6000)
        with self.assertRaises(ValueError) as ctx:
            ImageValidator.parse_header(p)
        self.assertIn("exceeds 50 Megapixel limit", str(ctx.exception))

    def test_reject_corrupt(self):
        p = self.d / "corrupt.png"
        p.write_bytes(b"not an image at all")
        with self.assertRaises(ValueError):
            ImageValidator.parse_header(p)


class TestMetadataStore(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.meta_file = Path(self.tmp_dir.name) / "metadata.json"
        # Patch Paths.metadata_file
        import backend
        self.orig_meta_path = backend.Paths.metadata_file
        backend.Paths.metadata_file = staticmethod(lambda: self.meta_file)
        self.store = MetadataStore()

    def tearDown(self):
        import backend
        backend.Paths.metadata_file = self.orig_meta_path
        self.tmp_dir.cleanup()

    def test_save_and_load(self):
        self.store.update_item("test:1", {"id": "test:1", "favorite": True})
        self.store.set_favorite("test:1", True)

        new_store = MetadataStore()
        self.assertTrue(new_store.is_favorite("test:1"))
        self.assertIn("test:1", new_store.data["items"])

    def test_toggle_favorite(self):
        res1 = self.store.toggle_favorite("item:A")
        self.assertTrue(res1)
        self.assertTrue(self.store.is_favorite("item:A"))

        res2 = self.store.toggle_favorite("item:A")
        self.assertFalse(res2)
        self.assertFalse(self.store.is_favorite("item:A"))

    def test_corruption_recovery(self):
        # Write corrupted JSON
        self.meta_file.write_text("{ broken json: ")
        store = MetadataStore()
        self.assertEqual(store.data["version"], 1)
        self.assertEqual(store.data["favorites"], [])
        # Check corrupt backup file exists
        backups = list(Path(self.tmp_dir.name).glob("metadata.json.corrupt.*"))
        self.assertGreaterEqual(len(backups), 1)

    def test_concurrent_writers_preserve_favorites_and_item_updates(self):
        context = multiprocessing.get_context("fork")
        start_barrier = context.Barrier(8)
        processes = [
            context.Process(
                target=_concurrent_metadata_writer,
                args=(str(self.meta_file), worker_id, start_barrier),
            )
            for worker_id in range(8)
        ]
        try:
            for process in processes:
                process.start()
            for process in processes:
                process.join(timeout=10)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)
                    self.fail("metadata writer deadlocked")
                self.assertEqual(process.exitcode, 0)
        finally:
            for process in processes:
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)

        result = MetadataStore().data
        expected = {f"worker:{worker_id}" for worker_id in range(8)}
        self.assertEqual(set(result["favorites"]), expected)
        self.assertEqual(set(result["items"]), expected)
        self.assertEqual(json.loads(self.meta_file.read_text())["version"], 1)


class TestFileSafety(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp_dir.name)

        import backend
        self.orig_global_dir = backend.Paths.global_wallpapers_dir
        self.orig_meta_file = backend.Paths.metadata_file
        self.orig_current_bg = backend.Paths.current_background_path
        self.orig_native_dir = backend.Paths.native_theme_backgrounds_dir
        self.orig_theme_name = backend.Paths.current_theme_name
        self.orig_thumb_path = backend.ThumbnailManager.get_thumbnail_path

        self.global_dir = self.d / "wallpapers"
        self.global_dir.mkdir(parents=True)
        self.meta_file = self.d / "metadata.json"

        backend.Paths.global_wallpapers_dir = staticmethod(lambda: self.global_dir)
        backend.Paths.metadata_file = staticmethod(lambda: self.meta_file)

    def tearDown(self):
        import backend
        backend.Paths.global_wallpapers_dir = self.orig_global_dir
        backend.Paths.metadata_file = self.orig_meta_file
        backend.Paths.current_background_path = self.orig_current_bg
        backend.Paths.native_theme_backgrounds_dir = self.orig_native_dir
        backend.Paths.current_theme_name = self.orig_theme_name
        backend.ThumbnailManager.get_thumbnail_path = self.orig_thumb_path
        self.tmp_dir.cleanup()

    def test_cannot_delete_active_wallpaper(self):
        import backend
        fake_bg = self.global_dir / "active.png"
        fake_bg.write_bytes(
            b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR"
            + struct.pack(">II", 2, 2) + b"\x08\x06\x00\x00\x00" + b"\x00" * 40
        )
        backend.Paths.current_background_path = staticmethod(lambda: str(fake_bg.resolve()))
        backend.ThumbnailManager.get_thumbnail_path = staticmethod(lambda _path: self.d / "missing-thumb.png")

        # System exit with CANNOT_DELETE_ACTIVE_WALLPAPER
        metadata = MetadataStore()
        catalog = WallpaperCatalog(metadata)
        output = StringIO()
        with unittest.mock.patch("backend.subprocess.run") as run, redirect_stdout(output):
            with self.assertRaises(SystemExit):
                FileManager.delete_wallpaper("global:active.png", catalog)
        self.assertEqual(json.loads(output.getvalue())["error"]["code"], "CANNOT_DELETE_ACTIVE_WALLPAPER")
        run.assert_not_called()

    def test_cannot_delete_theme_wallpaper(self):
        import backend
        native_dir = self.d / "native-theme"
        native_dir.mkdir()
        native_wallpaper = native_dir / "preset.png"
        native_wallpaper.write_bytes(
            b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR"
            + struct.pack(">II", 2, 2) + b"\x08\x06\x00\x00\x00" + b"\x00" * 40
        )
        backend.Paths.native_theme_backgrounds_dir = staticmethod(lambda: native_dir)
        backend.Paths.current_theme_name = staticmethod(lambda: "default")
        backend.Paths.current_background_path = staticmethod(lambda: None)
        backend.ThumbnailManager.get_thumbnail_path = staticmethod(lambda _path: self.d / "missing-thumb.png")
        metadata = MetadataStore()
        catalog = WallpaperCatalog(metadata)
        output = StringIO()
        with unittest.mock.patch("backend.subprocess.run") as run, redirect_stdout(output):
            with self.assertRaises(SystemExit):
                FileManager.delete_wallpaper("native:default:preset.png", catalog)
        self.assertEqual(json.loads(output.getvalue())["error"]["code"], "PERMISSION_DENIED")
        run.assert_not_called()



class TestFilterManager(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_apply_magick_filter(self):
        import backend
        # Create a small valid PNG
        p = self.d / "test_color.png"
        subprocess.run(["magick", "-size", "100x100", "xc:red", str(p)], check=True)
        self.assertTrue(p.is_file())

        # Convert to grayscale
        backend.FilterManager.apply_magick_filter(p, saturation=0, brightness=100)
        fmt, width, height, file_size = ImageValidator.parse_header(p)
        self.assertEqual(fmt, "png")
        self.assertEqual(width, 100)
        self.assertEqual(height, 100)

if __name__ == "__main__":
    unittest.main()
