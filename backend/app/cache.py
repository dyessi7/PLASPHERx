import hashlib
from pathlib import Path

CACHE_DIR = Path("/tmp/spherex_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def make_frame_key(src: str, ra: float, dec: float, fov: float) -> str:
    raw = f"{src}|{ra:.6f}|{dec:.6f}|{fov:.4f}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_cached_frame(key: str) -> bytes | None:
    path = CACHE_DIR / f"{key}.png"
    if path.exists():
        return path.read_bytes()
    return None


def save_cached_frame(key: str, data: bytes) -> None:
    path = CACHE_DIR / f"{key}.png"
    path.write_bytes(data)