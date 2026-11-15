import base64

_DUMMY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def search_images(ra: float, dec: float) -> list[dict]:
    """Mock implementation of IRSA SIA image search."""
    return [
        {
            "obs_id": f"spherex_mock_{i:02d}",
            "access_url": f"https://irsa.ipac.caltech.edu/ibe/data/spherex/mock_{i:02d}.fits",
            "mjd": 60811.96 + i * 2.5,
            "detector": f"D{(i % 6) + 1}",
        }
        for i in range(6)
    ]


def select_frames(rows: list[dict], detector: str, n: int) -> list[dict]:
    """Mock implementation of frame selection over time."""
    filtered = [r for r in rows if r["detector"] == detector]
    if not filtered:
        filtered = rows
    return filtered[:n]


def frame_png(access_url: str, ra: float, dec: float, fov: float) -> bytes:
    """Mock implementation of FITS cutout download, alignment, and PNG conversion."""
    return base64.b64decode(_DUMMY_PNG_B64)