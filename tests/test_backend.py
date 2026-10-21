import unittest
import os
import sys
import json
import tempfile
import struct
from pathlib import Path
import subprocess

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
        self.orig_meta_path = MetadataStore
        # Patch Paths.metadata_file
        import backend
        backend.Paths.metadata_file = staticmethod(lambda: self.meta_file)
        self.store = MetadataStore()

    def tearDown(self):
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


class TestFileSafety(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp_dir.name)

        import backend
        self.orig_global_dir = backend.Paths.global_wallpapers_dir
        self.orig_meta_file = backend.Paths.metadata_file
        self.orig_current_bg = backend.Paths.current_background_path

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
        self.tmp_dir.cleanup()

    def test_cannot_delete_active_wallpaper(self):
        import backend
        fake_bg = self.global_dir / "active.png"
        fake_bg.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
        backend.Paths.current_background_path = staticmethod(lambda: str(fake_bg.resolve()))

        # System exit with CANNOT_DELETE_ACTIVE_WALLPAPER
        metadata = MetadataStore()
        catalog = WallpaperCatalog(metadata)
        with self.assertRaises(SystemExit):
            FileManager.delete_wallpaper("global:active.png", catalog)

    def test_cannot_delete_theme_wallpaper(self):
        metadata = MetadataStore()
        catalog = WallpaperCatalog(metadata)
        with self.assertRaises(SystemExit):
            FileManager.delete_wallpaper("native:theme:bg.jpg", catalog)



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
