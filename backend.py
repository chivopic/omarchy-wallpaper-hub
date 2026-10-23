#!/usr/bin/env python3
"""
Omarchy Wallpaper Hub - Backend Engine (V1)
Unified CLI and service for wallpaper cataloging, switching, validation, and imports.
"""

import sys
import os
import json
import struct
import hashlib
import shutil
import tempfile
import subprocess
import argparse
import fcntl
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

SCHEMA_VERSION = 1
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MiB
MAX_PIXELS = 50_000_000          # 50 Megapixels
SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".webp"}

# Auto-detect WAYLAND_DISPLAY if unset
if "WAYLAND_DISPLAY" not in os.environ:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    if os.path.isdir(runtime_dir):
        sockets = [
            f for f in os.listdir(runtime_dir)
            if f.startswith("wayland-") and not f.endswith(".lock")
        ]
        if sockets:
            os.environ["WAYLAND_DISPLAY"] = sockets[0]


def success_response(data: Any) -> str:
    return json.dumps({
        "schemaVersion": SCHEMA_VERSION,
        "success": True,
        "data": data,
        "error": None
    }, ensure_ascii=False)


def error_response(code: str, message: str) -> str:
    return json.dumps({
        "schemaVersion": SCHEMA_VERSION,
        "success": False,
        "data": None,
        "error": {
            "code": code,
            "message": message
        }
    }, ensure_ascii=False)


def emit_success(data: Any):
    print(success_response(data))
    sys.exit(0)


def emit_error(code: str, message: str, exit_code: int = 1):
    sys.stderr.write(f"[{code}] {message}\n")
    print(error_response(code, message))
    sys.exit(exit_code)


class Paths:
    @staticmethod
    def data_dir() -> Path:
        base = os.environ.get("XDG_DATA_HOME")
        if base:
            p = Path(base) / "omarchy-wallpaper-hub"
        else:
            p = Path.home() / ".local" / "share" / "omarchy-wallpaper-hub"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @staticmethod
    def global_wallpapers_dir() -> Path:
        p = Paths.data_dir() / "wallpapers"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @staticmethod
    def pictures_wallpapers_dir() -> Path:
        return Path.home() / "Pictures" / "wallpapers"

    @staticmethod
    def metadata_file() -> Path:
        return Paths.data_dir() / "metadata.json"

    @staticmethod
    def cache_dir() -> Path:
        base = os.environ.get("XDG_CACHE_HOME")
        if base:
            p = Path(base) / "omarchy-wallpaper-hub"
        else:
            p = Path.home() / ".cache" / "omarchy-wallpaper-hub"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @staticmethod
    def thumbnails_dir() -> Path:
        p = Paths.cache_dir() / "thumbnails"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @staticmethod
    def current_theme_name() -> str:
        theme_file = Path.home() / ".local" / "state" / "omarchy" / "current" / "theme.name"
        if theme_file.is_file():
            try:
                name = theme_file.read_text().strip()
                if name:
                    return name
            except Exception:
                pass
        return "default"

    @staticmethod
    def native_theme_backgrounds_dir() -> Path:
        return Path.home() / ".local" / "state" / "omarchy" / "current" / "theme" / "backgrounds"

    @staticmethod
    def user_theme_backgrounds_dir(theme_name: Optional[str] = None) -> Path:
        if not theme_name:
            theme_name = Paths.current_theme_name()
        return Path.home() / ".config" / "omarchy" / "backgrounds" / theme_name

    @staticmethod
    def current_background_symlink() -> Path:
        return Path.home() / ".local" / "state" / "omarchy" / "current" / "background"

    @staticmethod
    def current_background_path() -> Optional[str]:
        link = Paths.current_background_symlink()
        try:
            if link.exists() or link.is_symlink():
                target = os.path.realpath(link)
                if os.path.isfile(target):
                    return target
        except Exception:
            pass
        return None


class ImageValidator:
    """Validates static PNG, JPEG, and WebP images via header examination."""

    @staticmethod
    def parse_header(file_path: Path) -> Tuple[str, int, int, int]:
        """
        Returns: (format, width, height, file_size)
        Raises ValueError if invalid, animated, corrupt, or exceeds limits.
        """
        if not file_path.is_file():
            raise ValueError(f"File does not exist: {file_path}")

        file_size = file_path.stat().st_size
        if file_size == 0:
            raise ValueError("File is empty (0 bytes)")
        if file_size > MAX_FILE_SIZE:
            raise ValueError(f"File size exceeds limit of 25 MiB ({file_size} bytes)")

        with open(file_path, "rb") as f:
            header = f.read(64)

            # PNG
            if header.startswith(b"\x89PNG\r\n\x1a\n"):
                if len(header) < 24:
                    raise ValueError("Truncated PNG header")
                width, height = struct.unpack(">II", header[16:24])
                fmt = "png"

            # JPEG
            elif header.startswith(b"\xff\xd8\xff"):
                fmt = "jpeg"
                f.seek(2)
                width, height = None, None
                while True:
                    marker_bytes = f.read(2)
                    if len(marker_bytes) < 2:
                        break
                    marker, = struct.unpack(">H", marker_bytes)
                    # SOF0, SOF1, SOF2, etc. (excluding DHT, DQT)
                    if (0xffc0 <= marker <= 0xffc3) or (0xffc9 <= marker <= 0xffcb):
                        f.read(3)  # length (2 bytes) + precision (1 byte)
                        dim_data = f.read(4)
                        if len(dim_data) == 4:
                            height, width = struct.unpack(">HH", dim_data)
                        break
                    else:
                        len_data = f.read(2)
                        if len(len_data) < 2:
                            break
                        seg_len, = struct.unpack(">H", len_data)
                        f.seek(seg_len - 2, os.SEEK_CUR)
                if width is None or height is None:
                    raise ValueError("Could not parse JPEG dimensions")

            # WebP
            elif header.startswith(b"RIFF") and header[8:12] == b"WEBP":
                tag = header[12:16]
                if tag == b"VP8 ":
                    f.seek(26)
                    dim_data = f.read(4)
                    if len(dim_data) < 4:
                        raise ValueError("Truncated VP8 WebP header")
                    w_raw, h_raw = struct.unpack("<HH", dim_data)
                    width, height = w_raw & 0x3fff, h_raw & 0x3fff
                    fmt = "webp"
                elif tag == b"VP8L":
                    f.seek(21)
                    dim_data = f.read(4)
                    if len(dim_data) < 4:
                        raise ValueError("Truncated VP8L WebP header")
                    val = struct.unpack("<I", dim_data)[0]
                    width = 1 + (val & 0x3fff)
                    height = 1 + ((val >> 14) & 0x3fff)
                    fmt = "webp"
                elif tag == b"VP8X":
                    flags = header[20]
                    # Bit 1 of flags is animation bit
                    if flags & 0x02:
                        raise ValueError("Animated WebP is not supported in V1")
                    f.seek(24)
                    dim_data = f.read(6)
                    if len(dim_data) < 6:
                        raise ValueError("Truncated VP8X WebP header")
                    width = 1 + int.from_bytes(dim_data[0:3], "little")
                    height = 1 + int.from_bytes(dim_data[3:6], "little")
                    fmt = "webp"
                else:
                    raise ValueError(f"Unsupported WebP chunk type: {tag}")

            elif header.startswith(b"GIF87a") or header.startswith(b"GIF89a"):
                raise ValueError("GIF files are not supported in V1")
            else:
                raise ValueError("Unsupported or corrupted image format (PNG, JPEG, WebP only)")

        if width <= 0 or height <= 0:
            raise ValueError(f"Invalid dimensions: {width}x{height}")

        pixels = width * height
        if pixels > MAX_PIXELS:
            raise ValueError(f"Image resolution {width}x{height} exceeds 50 Megapixel limit")

        return fmt, width, height, file_size

    @staticmethod
    def compute_hash(file_path: Path) -> str:
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()


class ThumbnailManager:
    @staticmethod
    def get_thumbnail_path(image_path: Path) -> Path:
        """Computes deterministic thumbnail path and generates if missing/stale."""
        try:
            stat = image_path.stat()
            key_src = f"{image_path.resolve()}:{stat.st_mtime}:{stat.st_size}"
        except Exception:
            key_src = str(image_path.resolve())

        key = hashlib.md5(key_src.encode("utf-8")).hexdigest()
        thumb_path = Paths.thumbnails_dir() / f"{key}.jpg"

        if thumb_path.is_file() and thumb_path.stat().st_size > 0:
            return thumb_path

        # Generate thumbnail via vipsthumbnail
        tmp_thumb = thumb_path.with_suffix(f".tmp.{os.getpid()}.jpg")
        try:
            # Generate 256px wide thumbnail preserving aspect ratio
            res = subprocess.run([
                "vipsthumbnail",
                str(image_path),
                "--size", "256x",
                "-o", str(tmp_thumb)
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            if res.returncode == 0 and tmp_thumb.is_file():
                tmp_thumb.replace(thumb_path)
                return thumb_path
        except Exception:
            pass
        finally:
            if tmp_thumb.exists():
                try:
                    tmp_thumb.unlink()
                except Exception:
                    pass

        return thumb_path


class MetadataStore:
    def __init__(self):
        self.file_path = Paths.metadata_file()
        self.data: Dict[str, Any] = {
            "version": 1,
            "favorites": [],
            "items": {}
        }
        self.load()

    def load(self):
        with self._locked():
            self._load_unlocked()

    @contextmanager
    def _locked(self):
        """Serialize metadata read-modify-write transactions across processes."""
        lock_path = self.file_path.with_name(f"{self.file_path.name}.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_path, "a", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _load_unlocked(self):
        if not self.file_path.is_file():
            self.data = {"version": 1, "favorites": [], "items": {}}
            return
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                content = json.load(f)
                if isinstance(content, dict) and content.get("version") == 1:
                    self.data = content
                else:
                    self._backup_corrupt("invalid_version")
        except Exception:
            self._backup_corrupt("json_parse_error")

    def _backup_corrupt(self, reason: str):
        try:
            bak = self.file_path.with_name(f"metadata.json.corrupt.{reason}.{int(os.getpid())}")
            shutil.copy2(self.file_path, bak)
        except Exception:
            pass
        self.data = {"version": 1, "favorites": [], "items": {}}

    def _save_unlocked(self):
        tmp_fd, tmp_path = tempfile.mkstemp(dir=str(self.file_path.parent), prefix="meta_tmp_")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, str(self.file_path))
        except Exception as e:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
            raise e

    def is_favorite(self, item_id: str) -> bool:
        return item_id in self.data.get("favorites", [])

    def set_favorite(self, item_id: str, is_fav: bool):
        with self._locked():
            self._load_unlocked()
            favs = set(self.data.get("favorites", []))
            if is_fav:
                favs.add(item_id)
            else:
                favs.discard(item_id)
            self.data["favorites"] = sorted(favs)

            # Also update in items if present
            if item_id in self.data.get("items", {}):
                self.data["items"][item_id]["favorite"] = is_fav
            self._save_unlocked()

    def toggle_favorite(self, item_id: str) -> bool:
        with self._locked():
            self._load_unlocked()
            new_state = item_id not in self.data.get("favorites", [])
            favs = set(self.data.get("favorites", []))
            if new_state:
                favs.add(item_id)
            else:
                favs.discard(item_id)
            self.data["favorites"] = sorted(favs)
            if item_id in self.data.get("items", {}):
                self.data["items"][item_id]["favorite"] = new_state
            self._save_unlocked()
            return new_state

    def update_item(self, item_id: str, item_data: Dict[str, Any]):
        with self._locked():
            self._load_unlocked()
            if "items" not in self.data:
                self.data["items"] = {}
            self.data["items"][item_id] = item_data
            self._save_unlocked()

    def remove_item(self, item_id: str):
        with self._locked():
            self._load_unlocked()
            if item_id in self.data.get("favorites", []):
                self.data["favorites"].remove(item_id)
            if item_id in self.data.get("items", {}):
                del self.data["items"][item_id]
            self._save_unlocked()


class WallpaperCatalog:
    def __init__(self, metadata: MetadataStore):
        self.metadata = metadata

    def scan_directory(self, directory: Path, source_type: str, theme_name: Optional[str] = None) -> List[Dict[str, Any]]:
        results = []
        if not directory.is_dir():
            return results

        current_bg = Paths.current_background_path()

        for entry in sorted(directory.iterdir()):
            if entry.is_symlink() or not entry.is_file():
                continue
            if entry.suffix.lower() not in SUPPORTED_EXTS:
                continue

            try:
                fmt, width, height, file_size = ImageValidator.parse_header(entry)
            except Exception:
                continue

            abs_path = str(entry.resolve())
            if source_type == "global":
                item_id = f"global:{entry.name}"
                can_delete = True
            elif source_type == "user-theme":
                item_id = f"theme:{theme_name}:{entry.name}"
                can_delete = True
            elif source_type == "pictures":
                item_id = f"pictures:{entry.name}"
                can_delete = False
            else:  # native-theme
                item_id = f"native:{theme_name}:{entry.name}"
                can_delete = False

            is_current = (current_bg is not None and os.path.samefile(abs_path, current_bg)) if current_bg else False
            is_fav = self.metadata.is_favorite(item_id)

            thumb = ThumbnailManager.get_thumbnail_path(entry)

            item = {
                "id": item_id,
                "name": entry.stem,
                "filename": entry.name,
                "path": abs_path,
                "thumbnail": str(thumb) if thumb.is_file() else "",
                "source": source_type,
                "theme": theme_name or "",
                "favorite": is_fav,
                "format": fmt,
                "width": width,
                "height": height,
                "size": file_size,
                "isCurrent": is_current,
                "canDelete": can_delete
            }
            results.append(item)
        return results

    def get_current_theme_items(self) -> List[Dict[str, Any]]:
        theme_name = Paths.current_theme_name()
        items = []

        # 1. Native theme wallpapers
        native_dir = Paths.native_theme_backgrounds_dir()
        items.extend(self.scan_directory(native_dir, "native-theme", theme_name))

        # 2. User theme wallpapers
        user_dir = Paths.user_theme_backgrounds_dir(theme_name)
        items.extend(self.scan_directory(user_dir, "user-theme", theme_name))

        return items

    def get_global_items(self) -> List[Dict[str, Any]]:
        global_dir = Paths.global_wallpapers_dir()
        items = list(self.scan_directory(global_dir, "global", None))
        pics_dir = Paths.pictures_wallpapers_dir()
        if pics_dir.is_dir() and pics_dir.resolve() != global_dir.resolve():
            items.extend(self.scan_directory(pics_dir, "pictures", None))
        return items

    def get_items(self, scope: str = "current-theme") -> List[Dict[str, Any]]:
        if scope == "global":
            return self.get_global_items()
        elif scope == "favorites":
            all_items = self.get_current_theme_items() + self.get_global_items()
            # Deduplicate by id
            seen = set()
            favs = []
            for it in all_items:
                if it["id"] not in seen and it["favorite"]:
                    seen.add(it["id"])
                    favs.append(it)
            return favs
        else:  # default: current-theme
            return self.get_current_theme_items()


class WallpaperController:
    @staticmethod
    def status(catalog: WallpaperCatalog) -> Dict[str, Any]:
        theme = Paths.current_theme_name()
        current_bg = Paths.current_background_path()

        theme_items = catalog.get_current_theme_items()
        global_items = catalog.get_global_items()
        fav_items = catalog.get_items("favorites")

        current_id = ""
        current_name = ""
        if current_bg:
            for item in theme_items + global_items:
                try:
                    if os.path.samefile(item["path"], current_bg):
                        current_id = item["id"]
                        current_name = item["name"]
                        break
                except Exception:
                    pass
            if not current_name:
                current_name = Path(current_bg).stem

        return {
            "theme": theme,
            "currentBackground": current_bg or "",
            "currentId": current_id,
            "currentName": current_name,
            "counts": {
                "currentTheme": len(theme_items),
                "global": len(global_items),
                "favorites": len(fav_items)
            }
        }

    @staticmethod
    def apply_wallpaper(image_path: str) -> Dict[str, Any]:
        target = Path(image_path).resolve()
        if not target.is_file():
            emit_error("FILE_NOT_FOUND", f"Target wallpaper does not exist: {target}")

        try:
            ImageValidator.parse_header(target)
        except Exception as e:
            emit_error("INVALID_IMAGE", f"Cannot apply invalid wallpaper: {e}")

        # Native First: execute omarchy theme bg set <abs_path>
        cmd = ["omarchy", "theme", "bg", "set", str(target)]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if res.returncode != 0:
                emit_error("CLI_ERROR", f"omarchy theme bg set failed: {res.stderr.strip() or res.stdout.strip()}")
        except Exception as e:
            emit_error("CLI_ERROR", f"Failed to execute omarchy CLI: {e}")

        # Validate symlink
        current = Paths.current_background_path()
        applied = (current is not None and os.path.samefile(current, str(target)))

        return {
            "applied": applied,
            "path": str(target),
            "current": current or ""
        }

    @staticmethod
    def cycle(catalog: WallpaperCatalog, scope: str, direction: int) -> Dict[str, Any]:
        """direction: 1 for next, -1 for previous"""
        items = catalog.get_items(scope)
        if not items:
            emit_error("EMPTY_LIBRARY", f"No wallpapers available in scope '{scope}'")

        current_bg = Paths.current_background_path()
        current_idx = -1
        if current_bg:
            for i, item in enumerate(items):
                try:
                    if os.path.samefile(item["path"], current_bg):
                        current_idx = i
                        break
                except Exception:
                    pass

        if current_idx == -1:
            next_idx = 0 if direction > 0 else (len(items) - 1)
        else:
            next_idx = (current_idx + direction) % len(items)

        chosen = items[next_idx]
        apply_res = WallpaperController.apply_wallpaper(chosen["path"])
        return {
            **apply_res,
            "item": chosen,
            "scope": scope,
            "index": next_idx,
            "total": len(items)
        }

    @staticmethod
    def random(catalog: WallpaperCatalog, scope: str) -> Dict[str, Any]:
        import random
        items = catalog.get_items(scope)
        if not items:
            emit_error("EMPTY_LIBRARY", f"No wallpapers available in scope '{scope}'")

        current_bg = Paths.current_background_path()
        candidates = []
        for it in items:
            try:
                if not (current_bg and os.path.samefile(it["path"], current_bg)):
                    candidates.append(it)
            except Exception:
                candidates.append(it)

        chosen = random.choice(candidates if candidates else items)
        apply_res = WallpaperController.apply_wallpaper(chosen["path"])
        return {
            **apply_res,
            "item": chosen,
            "scope": scope,
            "total": len(items)
        }


class ImportManager:
    @staticmethod
    def import_clipboard(target_scope: str = "global", auto_apply: bool = True, mono: bool = False, saturation: int = 0, brightness: int = 100) -> Dict[str, Any]:
        # 1. Query clipboard mime types via wl-paste -l
        try:
            res = subprocess.run(["wl-paste", "--list-types"], capture_output=True, text=True, timeout=3)
            if res.returncode != 0:
                emit_error("CLIPBOARD_ERROR", "Could not access Wayland clipboard")
            mimes = res.stdout.strip().splitlines()
        except Exception as e:
            emit_error("CLIPBOARD_ERROR", f"Failed to run wl-paste: {e}")

        # Check for URL string first to provide helpful message
        try:
            txt_res = subprocess.run(["wl-paste", "--type", "text/plain"], capture_output=True, text=True, timeout=2)
            if txt_res.returncode == 0:
                text_content = txt_res.stdout.strip()
                if text_content.startswith("http://") or text_content.startswith("https://"):
                    emit_error("URL_NOT_SUPPORTED_IN_V1", "Direct URL download is not supported in V1. Please copy the image directly or save it locally first.")
        except Exception:
            pass

        # Check for file uri-list
        if "text/uri-list" in mimes:
            try:
                uri_res = subprocess.run(["wl-paste", "--type", "text/uri-list"], capture_output=True, text=True, timeout=3)
                if uri_res.returncode == 0:
                    uris = [u.strip() for u in uri_res.stdout.strip().splitlines() if u.strip()]
                    if uris and uris[0].startswith("file://"):
                        local_file = Path(uris[0][7:])
                        return ImportManager.import_file(str(local_file), target_scope, auto_apply, origin="clipboard")
            except Exception:
                pass

        # Check for direct image mime types
        target_mime = None
        ext = None
        for m, e in [("image/png", ".png"), ("image/jpeg", ".jpg"), ("image/webp", ".webp")]:
            if m in mimes:
                target_mime = m
                ext = e
                break

        if not target_mime:
            emit_error("NO_IMAGE_IN_CLIPBOARD", "Clipboard does not contain a supported image (PNG, JPEG, WebP)")

        # Dump clipboard bytes to temp file
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)
            try:
                p = subprocess.run(["wl-paste", "--type", target_mime], stdout=tmp_file, stderr=subprocess.PIPE, timeout=5)
                if p.returncode != 0:
                    emit_error("CLIPBOARD_ERROR", "Failed to read image data from clipboard")
            except Exception as e:
                tmp_path.unlink(missing_ok=True)
                emit_error("CLIPBOARD_ERROR", f"Failed to dump clipboard: {e}")

        try:
            return ImportManager._save_validated_file(tmp_path, target_scope, auto_apply, ext, origin="clipboard", mono=mono, saturation=saturation, brightness=brightness)
        finally:
            if tmp_path.is_file():
                tmp_path.unlink(missing_ok=True)

    @staticmethod
    def import_file(src_path: str, target_scope: str = "global", auto_apply: bool = True, origin: str = "file", mono: bool = False, saturation: int = 0, brightness: int = 100) -> Dict[str, Any]:
        src = Path(src_path).resolve()
        if not src.is_file():
            emit_error("FILE_NOT_FOUND", f"Source file not found: {src}")

        ext = src.suffix.lower()
        if ext == ".jpeg":
            ext = ".jpg"
        if ext not in SUPPORTED_EXTS:
            emit_error("UNSUPPORTED_FORMAT", f"Format {ext} is not supported in V1 (PNG, JPEG, WebP only)")

        if mono:
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)
            try:
                shutil.copy2(src, tmp_path)
                return ImportManager._save_validated_file(tmp_path, target_scope, auto_apply, ext, origin=origin, mono=True, saturation=saturation, brightness=brightness)
            finally:
                if tmp_path.is_file():
                    tmp_path.unlink(missing_ok=True)
        else:
            return ImportManager._save_validated_file(src, target_scope, auto_apply, ext, origin=origin)

    @staticmethod
    def _save_validated_file(src_path: Path, target_scope: str, auto_apply: bool, ext: str, origin: str, mono: bool = False, saturation: int = 0, brightness: int = 100) -> Dict[str, Any]:
        if mono:
            FilterManager.apply_magick_filter(src_path, saturation=saturation, brightness=brightness)
        # Validate image
        try:
            fmt, width, height, file_size = ImageValidator.parse_header(src_path)
            content_hash = ImageValidator.compute_hash(src_path)
        except Exception as e:
            emit_error("INVALID_IMAGE", str(e))

        # Target directory
        theme_name = Paths.current_theme_name()
        if target_scope == "theme":
            dest_dir = Paths.user_theme_backgrounds_dir(theme_name)
            dest_dir.mkdir(parents=True, exist_ok=True)
            source_type = "user-theme"
        else:
            dest_dir = Paths.global_wallpapers_dir()
            source_type = "global"

        # Check deduplication
        target_stem = f"wp_{content_hash[:12]}"
        dest_filename = f"{target_stem}{ext}"
        dest_path = dest_dir / dest_filename

        is_duplicate = False
        if dest_path.is_file():
            is_duplicate = True
        else:
            # Atomic copy
            tmp_dest = dest_dir / f".tmp_{os.getpid()}_{dest_filename}"
            try:
                shutil.copy2(src_path, tmp_dest)
                tmp_dest.replace(dest_path)
            except Exception as e:
                if tmp_dest.exists():
                    tmp_dest.unlink(missing_ok=True)
                emit_error("FILE_WRITE_ERROR", f"Failed to save image to {dest_dir}: {e}")

        # Update metadata
        metadata = MetadataStore()
        item_id = f"global:{dest_filename}" if source_type == "global" else f"theme:{theme_name}:{dest_filename}"
        metadata.update_item(item_id, {
            "id": item_id,
            "source": source_type,
            "path": str(dest_path.resolve()),
            "theme": theme_name if source_type == "user-theme" else "",
            "favorite": metadata.is_favorite(item_id),
            "hash": content_hash,
            "importedAt": int(Path(dest_path).stat().st_mtime),
            "origin": origin
        })

        thumb = ThumbnailManager.get_thumbnail_path(dest_path)

        result_item = {
            "id": item_id,
            "name": dest_path.stem,
            "filename": dest_filename,
            "path": str(dest_path.resolve()),
            "thumbnail": str(thumb) if thumb.is_file() else "",
            "source": source_type,
            "theme": theme_name if source_type == "user-theme" else "",
            "favorite": metadata.is_favorite(item_id),
            "width": width,
            "height": height,
            "size": file_size,
            "isDuplicate": is_duplicate
        }

        applied = False
        if auto_apply:
            apply_res = WallpaperController.apply_wallpaper(str(dest_path.resolve()))
            applied = apply_res.get("applied", False)

        return {
            "item": result_item,
            "applied": applied,
            "isDuplicate": is_duplicate
        }


class FileManager:
    @staticmethod
    def delete_wallpaper(item_id: str, catalog: WallpaperCatalog) -> Dict[str, Any]:
        """Safely trashes a plugin-managed global wallpaper using gio trash."""
        all_items = catalog.get_current_theme_items() + catalog.get_global_items()
        items_by_id = {it["id"]: it for it in all_items}
        if item_id not in items_by_id:
            emit_error("FILE_NOT_FOUND", f"Item not found: {item_id}")

        item = items_by_id[item_id]
        if not item.get("canDelete"):
            emit_error("PERMISSION_DENIED", "Only plugin-managed global or user theme wallpapers can be deleted. Native theme wallpapers are protected.")

        target_path = Path(item["path"]).resolve()

        # Cannot delete active wallpaper
        current_bg = Paths.current_background_path()
        if current_bg and os.path.samefile(str(target_path), current_bg):
            emit_error("CANNOT_DELETE_ACTIVE_WALLPAPER", "Cannot delete the wallpaper currently in use. Please switch to another wallpaper first.")

        # Ensure path is strictly inside global wallpapers directory or user theme backgrounds directory
        global_dir = Paths.global_wallpapers_dir().resolve()
        user_theme_dir = Paths.user_theme_backgrounds_dir().resolve()
        is_global = str(target_path).startswith(str(global_dir))
        is_user_theme = str(target_path).startswith(str(user_theme_dir))
        if not (is_global or is_user_theme):
            emit_error("SECURITY_VIOLATION", "Target file is outside deletable directories")

        # Send to trash via gio trash
        try:
            res = subprocess.run(["gio", "trash", str(target_path)], capture_output=True, text=True, timeout=5)
            if res.returncode != 0:
                emit_error("TRASH_FAILED", f"Failed to trash file: {res.stderr.strip() or 'gio trash returned non-zero'}")
        except Exception as e:
            emit_error("TRASH_FAILED", f"Could not execute gio trash: {e}")

        # Clean metadata and thumbnail
        metadata = MetadataStore()
        metadata.remove_item(item_id)

        thumb = ThumbnailManager.get_thumbnail_path(target_path)
        if thumb.is_file():
            try:
                thumb.unlink()
            except Exception:
                pass

        return {
            "deletedId": item_id,
            "path": str(target_path)
        }

    @staticmethod
    def pick_file() -> Optional[str]:
        """Opens zenity file selection dialog."""
        try:
            res = subprocess.run([
                "zenity",
                "--file-selection",
                "--title=Select Wallpaper",
                "--file-filter=Image files (PNG, JPEG, WebP) | *.png *.jpg *.jpeg *.webp",
                "--file-filter=All files | *"
            ], capture_output=True, text=True, timeout=60)
            if res.returncode == 0:
                path = res.stdout.strip()
                if path:
                    return path
        except Exception:
            pass
        return None

class FilterManager:
    @staticmethod
    def apply_magick_filter(img_path: Path, saturation: int = 0, brightness: int = 100):
        cmd = ["magick", str(img_path.resolve())]
        if saturation == 0:
            if brightness == 100:
                cmd.extend(["-colorspace", "Gray"])
            else:
                cmd.extend(["-colorspace", "Gray", "-modulate", f"{brightness},0"])
        else:
            cmd.extend(["-modulate", f"{brightness},{saturation}"])
        cmd.append(str(img_path.resolve()))
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if res.returncode != 0:
            emit_error("CONVERT_FAILED", f"ImageMagick failed: {res.stderr.strip() or 'unknown error'}")

    @staticmethod
    def convert_mono(
        target: str,
        catalog: WallpaperCatalog,
        saturation: int = 0,
        brightness: int = 100,
        target_scope: str = "theme",
        auto_apply: bool = True
    ) -> Dict[str, Any]:
        target_path: Optional[Path] = None
        if target == "current":
            current_path = Paths.current_background_path()
            if current_path:
                target_path = Path(current_path)
        else:
            target_p = Path(target)
            if target_p.is_file():
                target_path = target_p
            else:
                all_items = catalog.get_current_theme_items() + catalog.get_global_items()
                for it in all_items:
                    if it["id"] == target:
                        target_path = Path(it["path"])
                        break

        if not target_path or not target_path.is_file():
            emit_error("FILE_NOT_FOUND", f"Target image not found: {target}")

        theme_name = Paths.current_theme_name()
        if target_scope == "theme":
            dest_dir = Paths.user_theme_backgrounds_dir(theme_name)
            source_type = "user-theme"
        else:
            dest_dir = Paths.global_wallpapers_dir()
            source_type = "global"
        dest_dir.mkdir(parents=True, exist_ok=True)

        ext = target_path.suffix.lower()
        if ext == ".jpeg":
            ext = ".jpg"
        stem = target_path.stem
        if stem.endswith("-mono"):
            stem = stem[:-5]

        if saturation == 0 and brightness == 100:
            dest_filename = f"{stem}-mono{ext}"
        else:
            dest_filename = f"{stem}-s{saturation}-b{brightness}{ext}"

        dest_path = dest_dir / dest_filename

        # Convert to dest_path
        cmd = ["magick", str(target_path.resolve())]
        if saturation == 0:
            if brightness == 100:
                cmd.extend(["-colorspace", "Gray"])
            else:
                cmd.extend(["-colorspace", "Gray", "-modulate", f"{brightness},0"])
        else:
            cmd.extend(["-modulate", f"{brightness},{saturation}"])
        cmd.append(str(dest_path.resolve()))

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if res.returncode != 0:
                emit_error("CONVERT_FAILED", f"ImageMagick failed: {res.stderr.strip() or 'unknown error'}")
        except Exception as e:
            emit_error("CONVERT_FAILED", f"Failed to execute magick: {e}")

        # Metadata & thumbnail
        metadata = MetadataStore()
        item_id = f"theme:{theme_name}:{dest_filename}" if source_type == "user-theme" else f"global:{dest_filename}"
        content_hash = ImageValidator.compute_hash(dest_path)
        fmt, width, height, file_size = ImageValidator.parse_header(dest_path)

        metadata.update_item(item_id, {
            "id": item_id,
            "source": source_type,
            "path": str(dest_path.resolve()),
            "theme": theme_name if source_type == "user-theme" else "",
            "favorite": metadata.is_favorite(item_id),
            "hash": content_hash,
            "importedAt": int(dest_path.stat().st_mtime),
            "origin": "filter"
        })

        thumb = ThumbnailManager.get_thumbnail_path(dest_path)

        result_item = {
            "id": item_id,
            "name": dest_path.stem,
            "filename": dest_filename,
            "path": str(dest_path.resolve()),
            "thumbnail": str(thumb) if thumb.is_file() else "",
            "source": source_type,
            "theme": theme_name if source_type == "user-theme" else "",
            "favorite": metadata.is_favorite(item_id),
            "width": width,
            "height": height,
            "size": file_size,
            "canDelete": True
        }

        applied = False
        if auto_apply:
            apply_res = WallpaperController.apply_wallpaper(str(dest_path.resolve()))
            applied = apply_res.get("applied", False)

        return {
            "item": result_item,
            "applied": applied
        }


def main():
    parser = argparse.ArgumentParser(description="Omarchy Wallpaper Hub Backend Engine")
    subparsers = parser.add_subparsers(dest="command")

    # status
    subparsers.add_parser("status", help="Get current theme and wallpaper status")

    # list
    list_p = subparsers.add_parser("list", help="List wallpapers in catalog")
    list_p.add_argument("--scope", choices=["current-theme", "global", "favorites"], default="current-theme")

    # apply
    apply_p = subparsers.add_parser("apply", help="Apply a wallpaper")
    apply_p.add_argument("target", help="Absolute path or item ID")

    # next
    next_p = subparsers.add_parser("next", help="Switch to next wallpaper")
    next_p.add_argument("--scope", choices=["current-theme", "global", "favorites"], default="current-theme")

    # previous
    prev_p = subparsers.add_parser("previous", help="Switch to previous wallpaper")
    prev_p.add_argument("--scope", choices=["current-theme", "global", "favorites"], default="current-theme")

    # random
    rand_p = subparsers.add_parser("random", help="Switch to a random wallpaper")
    rand_p.add_argument("--scope", choices=["current-theme", "global", "favorites"], default="current-theme")

    # import-clipboard
    clip_p = subparsers.add_parser("import-clipboard", help="Import wallpaper from clipboard")
    clip_p.add_argument("--target", choices=["global", "theme"], default="global")
    clip_p.add_argument("--no-apply", action="store_true", help="Do not apply automatically")
    clip_p.add_argument("--mono", action="store_true", help="Convert to grayscale on import")
    clip_p.add_argument("--saturation", type=int, default=0, help="Saturation (0=mono, 100=color)")
    clip_p.add_argument("--brightness", type=int, default=100, help="Brightness percentage (50-100)")

    # import-file
    file_p = subparsers.add_parser("import-file", help="Import wallpaper from file")
    file_p.add_argument("path", help="Path to image file")
    file_p.add_argument("--target", choices=["global", "theme"], default="global")
    file_p.add_argument("--no-apply", action="store_true", help="Do not apply automatically")
    file_p.add_argument("--mono", action="store_true", help="Convert to grayscale on import")
    file_p.add_argument("--saturation", type=int, default=0, help="Saturation (0=mono, 100=color)")
    file_p.add_argument("--brightness", type=int, default=100, help="Brightness percentage (50-100)")

    # convert-mono
    mono_p = subparsers.add_parser("convert-mono", help="Convert wallpaper to grayscale / dark mono")
    mono_p.add_argument("target", help="Item ID, absolute path, or 'current'")
    mono_p.add_argument("--saturation", type=int, default=0, help="Saturation (0=mono, 100=color)")
    mono_p.add_argument("--brightness", type=int, default=100, help="Brightness percentage (50-100)")
    mono_p.add_argument("--target-scope", choices=["theme", "global"], default="theme")
    mono_p.add_argument("--no-apply", action="store_true", help="Do not apply automatically")

    # favorite
    fav_p = subparsers.add_parser("favorite", help="Toggle or set favorite")
    fav_p.add_argument("id", help="Item ID")
    fav_p.add_argument("--toggle", action="store_true", default=True)
    fav_p.add_argument("--set", action="store_true")
    fav_p.add_argument("--unset", action="store_true")

    # delete
    del_p = subparsers.add_parser("delete", help="Safely trash a global wallpaper")
    del_p.add_argument("id", help="Item ID")

    # refresh
    subparsers.add_parser("refresh", help="Rescan wallpapers and regenerate missing thumbnails")

    # pick-file
    subparsers.add_parser("pick-file", help="Open zenity file picker and output selected path")

    args = parser.parse_args()

    if not args.command:
        parser.print_help(sys.stderr)
        emit_error("MISSING_COMMAND", "No command specified")

    metadata = MetadataStore()
    catalog = WallpaperCatalog(metadata)

    if args.command == "status":
        emit_success(WallpaperController.status(catalog))

    elif args.command == "list":
        emit_success(catalog.get_items(args.scope))

    elif args.command == "apply":
        target = args.target
        # Check if target is an item ID
        all_items = catalog.get_items("current-theme") + catalog.get_items("global")
        for item in all_items:
            if item["id"] == target:
                target = item["path"]
                break
        emit_success(WallpaperController.apply_wallpaper(target))

    elif args.command == "next":
        emit_success(WallpaperController.cycle(catalog, args.scope, direction=1))

    elif args.command == "previous":
        emit_success(WallpaperController.cycle(catalog, args.scope, direction=-1))

    elif args.command == "random":
        emit_success(WallpaperController.random(catalog, args.scope))

    elif args.command == "convert-mono":
        auto_apply = not args.no_apply
        emit_success(FilterManager.convert_mono(
            args.target,
            catalog,
            saturation=args.saturation,
            brightness=args.brightness,
            target_scope=args.target_scope,
            auto_apply=auto_apply
        ))

    elif args.command == "import-clipboard":
        auto_apply = not args.no_apply
        emit_success(ImportManager.import_clipboard(
            args.target,
            auto_apply,
            mono=getattr(args, "mono", False),
            saturation=getattr(args, "saturation", 0),
            brightness=getattr(args, "brightness", 100)
        ))

    elif args.command == "import-file":
        auto_apply = not args.no_apply
        emit_success(ImportManager.import_file(
            args.path,
            args.target,
            auto_apply,
            mono=getattr(args, "mono", False),
            saturation=getattr(args, "saturation", 0),
            brightness=getattr(args, "brightness", 100)
        ))
    elif args.command == "favorite":
        if args.set:
            metadata.set_favorite(args.id, True)
            is_fav = True
        elif args.unset:
            metadata.set_favorite(args.id, False)
            is_fav = False
        else:
            is_fav = metadata.toggle_favorite(args.id)
        emit_success({"id": args.id, "favorite": is_fav})

    elif args.command == "delete":
        emit_success(FileManager.delete_wallpaper(args.id, catalog))

    elif args.command == "refresh":
        # Force thumbnail scan for all scopes
        for scope in ["current-theme", "global"]:
            items = catalog.get_items(scope)
            for it in items:
                p = Path(it["path"])
                ThumbnailManager.get_thumbnail_path(p)
        emit_success(WallpaperController.status(catalog))

    elif args.command == "pick-file":
        chosen = FileManager.pick_file()
        if chosen:
            emit_success({"selected": chosen})
        else:
            emit_error("CANCELLED", "File selection cancelled", exit_code=0)

    else:
        emit_error("UNKNOWN_COMMAND", f"Unknown command {args.command}")


if __name__ == "__main__":
    main()
