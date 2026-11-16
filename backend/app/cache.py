import hashlib
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)
_cache_write_lock = threading.Lock()

FRAMES_DIR = settings.CACHE_DIR / "frames"
METADATA_DIR = settings.CACHE_DIR / "metadata"
FITS_DIR = settings.CACHE_DIR / "fits"

FRAMES_DIR.mkdir(parents=True, exist_ok=True)
METADATA_DIR.mkdir(parents=True, exist_ok=True)
FITS_DIR.mkdir(parents=True, exist_ok=True)


def is_cache_writable() -> bool:
    """Checks whether the cache directory has write permissions."""
    test_file = settings.CACHE_DIR / ".write_test"
    try:
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def get_cache_stats() -> dict[str, int]:
    """Returns the number of elements stored across each cache tier."""
    try:
        frames_count = len(list(FRAMES_DIR.glob("*.png")))
        metadata_count = len(list(METADATA_DIR.glob("*.json")))
        fits_count = len(list(FITS_DIR.glob("*.fits")))
        return {
            "cached_png_frames": frames_count,
            "cached_metadata_queries": metadata_count,
            "cached_raw_fits": fits_count,
        }
    except Exception:
        return {
            "cached_png_frames": 0,
            "cached_metadata_queries": 0,
            "cached_raw_fits": 0,
        }


def make_frame_key(src: str, ra: float, dec: float, fov: float, ref: str | None = None) -> str:
    """Generates a deterministic SHA-256 key for a specific cropped PNG frame."""
    from app.spherex import RENDER_VERSION  # stale renders must not be served

    raw = json.dumps(["png", RENDER_VERSION, src, ra, dec, fov, ref], separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_cutout_key(src: str, ra: float, dec: float, fov: float) -> str:
    """Generates a deterministic SHA-256 key for a raw FITS cutout from IRSA."""
    raw = json.dumps(["fits", src, ra, dec, fov], separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_query_key(ra: float, dec: float, fov: float, detector: str, n: int) -> str:
    """Generates a deterministic SHA-256 key for a frame metadata query."""
    from app.spherex import RENDER_VERSION  # cached payload embeds versioned frame URLs

    raw = json.dumps(["query", RENDER_VERSION, ra, dec, fov, detector, n], separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_search_key(ra: float, dec: float) -> str:
    """Generates a deterministic key for an IRSA image search."""
    raw = json.dumps(["search", ra, dec], separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_files() -> list[Path]:
    return (
        list(FRAMES_DIR.glob("*.png"))
        + list(METADATA_DIR.glob("*.json"))
        + list(FITS_DIR.glob("*.fits"))
    )


def _save_cache_file(directory: Path, filename: str, data: bytes) -> None:
    path = directory / filename
    max_bytes = settings.CACHE_MAX_BYTES
    if len(data) > max_bytes:
        logger.warning("Skipping cache entry larger than SPHEREX_CACHE_MAX_BYTES: %s", path)
        return

    with _cache_write_lock:
        try:
            files = _cache_files()
            sizes = {item: item.stat().st_size for item in files}
            total_size = sum(sizes.values()) - sizes.get(path, 0)
            for oldest in sorted(files, key=lambda item: item.stat().st_mtime):
                if total_size + len(data) <= max_bytes:
                    break
                if oldest == path:
                    continue
                size = sizes[oldest]
                oldest.unlink(missing_ok=True)
                total_size -= size

            # Atomic write via temp file in the same directory
            tmp_path = directory / f"{filename}.tmp.{threading.get_ident()}_{time.time_ns()}"
            tmp_path.write_bytes(data)
            tmp_path.replace(path)
        except OSError as exc:
            logger.warning("Unable to update cache entry %s: %s", path, exc)


def _touch_lru(path: Path) -> None:
    """Updates access and modification time to implement true LRU eviction."""
    try:
        time_now = time.time()
        import os
        os.utime(path, (time_now, time_now))
    except OSError:
        pass


def get_cached_frame(key: str) -> bytes | None:
    """Retrieves the bytes of a cached PNG file if present."""
    path = FRAMES_DIR / f"{key}.png"
    if path.is_file():
        try:
            data = path.read_bytes()
            _touch_lru(path)
            return data
        except OSError as exc:
            logger.warning("Unable to read cached frame %s: %s", path, exc)
            return None
    return None


def save_cached_frame(key: str, data: bytes) -> None:
    """Saves processed PNG frame bytes to disk cache."""
    _save_cache_file(FRAMES_DIR, f"{key}.png", data)


def save_cached_frame_meta(key: str, meta: dict[str, Any]) -> None:
    """Saves lightweight metadata (wavelength, saturation, contamination flags) for a cached frame."""
    try:
        encoded = json.dumps(meta).encode("utf-8")
        _save_cache_file(FRAMES_DIR, f"{key}.meta.json", encoded)
    except Exception as exc:
        logger.warning("Unable to save frame meta for %s: %s", key, exc)


def get_cached_frame_meta(key: str) -> dict[str, Any] | None:
    """Retrieves cached frame metadata if present."""
    path = FRAMES_DIR / f"{key}.meta.json"
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def get_cached_fits(key: str) -> bytes | None:
    """Retrieves cached raw FITS cutout bytes if present."""
    path = FITS_DIR / f"{key}.fits"
    if path.is_file():
        try:
            data = path.read_bytes()
            _touch_lru(path)
            return data
        except OSError as exc:
            logger.warning("Unable to read cached FITS %s: %s", path, exc)
            return None
    return None


def save_cached_fits(key: str, data: bytes) -> None:
    """Saves raw FITS cutout bytes to disk cache."""
    _save_cache_file(FITS_DIR, f"{key}.fits", data)


def get_cached_metadata(key: str, max_age_seconds: int | None = None) -> Any | None:
    """Retrieves cached JSON metadata if not expired by TTL."""
    if max_age_seconds is None:
        max_age_seconds = settings.METADATA_CACHE_TTL_SECONDS

    path = METADATA_DIR / f"{key}.json"
    if not path.is_file():
        return None

    try:
        mtime = path.stat().st_mtime
        # Expired entries stay on disk (the size limit evicts them) so they can
        # still be served as a fallback while IRSA is unavailable.
        if (time.time() - mtime) > max_age_seconds:
            return None

        content = path.read_text(encoding="utf-8")
        data = json.loads(content)
        _touch_lru(path)
        return data
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Unable to read cached metadata %s: %s", path, exc)
        return None


def save_cached_metadata(key: str, data: Any) -> None:
    """Saves serializable JSON data in metadata cache."""
    try:
        encoded = json.dumps(data, indent=2).encode("utf-8")
    except (TypeError, ValueError) as exc:
        logger.warning("Unable to serialize metadata cache entry %s: %s", key, exc)
        return
    _save_cache_file(METADATA_DIR, f"{key}.json", encoded)
