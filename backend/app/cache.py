import hashlib
import json
import time
from pathlib import Path
from app.config import get_settings

settings = get_settings()

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


def make_frame_key(src: str, ra: float, dec: float, fov: float) -> str:
    """Generates a deterministic SHA-256 key for a specific cropped PNG frame."""
    # Includes the render version so PNGs rendered by older code are not served.
    from app.spherex import RENDER_VERSION

    raw = f"png-v{RENDER_VERSION}|{src}|{ra:.6f}|{dec:.6f}|{fov:.4f}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_cutout_key(src: str, ra: float, dec: float, fov: float) -> str:
    """Generates a deterministic SHA-256 key for a raw FITS cutout from IRSA."""
    raw = f"fits|{src}|{ra:.6f}|{dec:.6f}|{fov:.4f}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_query_key(ra: float, dec: float, fov: float, detector: str, n: int) -> str:
    """Generates a deterministic SHA-256 key for a frame metadata query."""
    # The cached /api/frames payload embeds frame URLs, which carry the render version.
    from app.spherex import RENDER_VERSION

    raw = f"query-v{RENDER_VERSION}|{ra:.5f}|{dec:.5f}|{fov:.4f}|{detector}|{n}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_cached_frame(key: str) -> bytes | None:
    """Retrieves the bytes of a cached PNG file if present."""
    path = FRAMES_DIR / f"{key}.png"
    if path.is_file():
        try:
            return path.read_bytes()
        except OSError:
            return None
    return None


def save_cached_frame(key: str, data: bytes) -> None:
    """Saves processed PNG frame bytes to disk cache."""
    path = FRAMES_DIR / f"{key}.png"
    try:
        path.write_bytes(data)
    except OSError:
        pass


def get_cached_fits(key: str) -> bytes | None:
    """Retrieves cached raw FITS cutout bytes if present."""
    path = FITS_DIR / f"{key}.fits"
    if path.is_file():
        try:
            return path.read_bytes()
        except OSError:
            return None
    return None


def save_cached_fits(key: str, data: bytes) -> None:
    """Saves raw FITS cutout bytes to disk cache."""
    path = FITS_DIR / f"{key}.fits"
    try:
        path.write_bytes(data)
    except OSError:
        pass


def get_cached_metadata(key: str, max_age_seconds: int | None = None) -> dict | None:
    """Retrieves cached JSON metadata if not expired by TTL."""
    if max_age_seconds is None:
        max_age_seconds = settings.METADATA_CACHE_TTL_SECONDS

    path = METADATA_DIR / f"{key}.json"
    if not path.is_file():
        return None

    try:
        mtime = path.stat().st_mtime
        if (time.time() - mtime) > max_age_seconds:
            path.unlink(missing_ok=True)
            return None

        content = path.read_text(encoding="utf-8")
        return json.loads(content)
    except Exception:
        return None


def save_cached_metadata(key: str, data: dict) -> None:
    """Saves a serializable dictionary as JSON in metadata cache."""
    path = METADATA_DIR / f"{key}.json"
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass
