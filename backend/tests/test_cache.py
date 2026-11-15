from concurrent.futures import ThreadPoolExecutor
import os
import time

from app import cache, spherex
from app.config import get_settings


def test_search_images_cache_keeps_results_for_ttl(monkeypatch, tmp_path):
    monkeypatch.setattr(cache, "METADATA_DIR", tmp_path)
    monkeypatch.setattr(get_settings(), "SEARCH_CACHE_TTL_SECONDS", 600)
    calls = []

    def search(ra, dec):
        calls.append((ra, dec))
        return []

    monkeypatch.setattr(spherex, "_search_images_uncached", search)
    assert spherex.search_images(12.5, -4.25) == []
    assert spherex.search_images(12.5, -4.25) == []
    assert calls == [(12.5, -4.25)]

    entry = tmp_path / f"{cache.make_search_key(12.5, -4.25)}.json"
    os.utime(entry, (time.time() - 601, time.time() - 601))
    assert spherex.search_images(12.5, -4.25) == []
    assert calls == [(12.5, -4.25), (12.5, -4.25)]


def test_cache_evicts_old_entries_to_stay_under_size_limit(monkeypatch, tmp_path):
    frames_dir = tmp_path / "frames"
    metadata_dir = tmp_path / "metadata"
    fits_dir = tmp_path / "fits"
    for directory in (frames_dir, metadata_dir, fits_dir):
        directory.mkdir()

    monkeypatch.setattr(cache, "FRAMES_DIR", frames_dir)
    monkeypatch.setattr(cache, "METADATA_DIR", metadata_dir)
    monkeypatch.setattr(cache, "FITS_DIR", fits_dir)
    monkeypatch.setattr(get_settings(), "CACHE_MAX_BYTES", 5)

    cache.save_cached_frame("old", b"123")
    os.utime(frames_dir / "old.png", (1, 1))
    cache.save_cached_fits("new", b"456")

    assert not (frames_dir / "old.png").exists()
    assert (fits_dir / "new.fits").read_bytes() == b"456"


def test_concurrent_cutout_requests_share_one_fetch(monkeypatch, tmp_path):
    fits_dir = tmp_path / "fits"
    fits_dir.mkdir()
    monkeypatch.setattr(cache, "FITS_DIR", fits_dir)
    calls = []

    def fetch_uncached(access_url, ra, dec, fov):
        calls.append(access_url)
        time.sleep(0.02)
        data = b"raw fits bytes"
        cache.save_cached_fits(cache.make_cutout_key(access_url, ra, dec, fov), data)
        return data

    monkeypatch.setattr(spherex, "_fetch_cutout_uncached", fetch_uncached)
    args = ("https://irsa.ipac.caltech.edu/image.fits", 12.5, -4.25, 0.1)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: spherex.fetch_cutout(*args), range(4)))

    assert results == [b"raw fits bytes"] * 4
    assert calls == [args[0]]
