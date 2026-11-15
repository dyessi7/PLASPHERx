import base64
import io
import logging
import math
import time
import urllib.error
import http.client
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import imageio.v2 as imageio
import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS
from astropy.utils.data import conf
from reproject import reproject_interp

from app import cache
from app.config import get_settings

# Configure logging and suppress minor astropy/wcs warnings
logging.getLogger("astropy").setLevel(logging.ERROR)
logging.getLogger("reproject").setLevel(logging.ERROR)

settings = get_settings()
conf.remote_timeout = settings.IRSA_TIMEOUT_SECONDS

# SPHEREx plate scale: 6.15 arcseconds per pixel
SPHEREX_PIXEL_SCALE_DEG = 6.15 / 3600.0
SPHEREX_PIXEL_SCALE_ARCSEC = 6.15

# Solid angle of one pixel in steradians; images are in MJy/sr.
SPHEREX_PIXEL_SR = math.radians(SPHEREX_PIXEL_SCALE_DEG) ** 2

SPECTRUM_FLUX_UNIT = "mJy"
SPECTRUM_APERTURE_RADIUS_PIXELS = 2


def _mjd_to_iso_date(mjd: float) -> str:
    """Converts Modified Julian Date (MJD) to ISO YYYY-MM-DD string."""
    unix_seconds = (mjd - 40587.0) * 86400.0
    return datetime.fromtimestamp(unix_seconds, tz=timezone.utc).strftime("%Y-%m-%d")


def search_images(ra: float, dec: float) -> list[dict[str, Any]]:
    """Queries available images in IRSA SIA (SPHEREx DR1 and QR3)

    for given coordinates, sorted chronologically.
    """
    coord = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame="icrs")
    try:
        from astroquery.ipac.irsa import Irsa

        res = Irsa.query_sia(
            pos=(coord, 1 * u.arcsec),
            collection=["spherex_dr1", "spherex_qr3"],
        )
        table = res.to_table() if hasattr(res, "to_table") else res
    except Exception as irsa_err:
        # Fallback: Check if coordinates match a local target with manifest.csv
        from app import targets

        matched = targets.find_target_by_coords(ra, dec, tolerance_deg=0.05)
        if matched:
            local_manifest = settings.RAW_FITS_DIR / matched.id / "manifest.csv"
            if local_manifest.is_file():
                import pandas as pd

                df = pd.read_csv(local_manifest)
                rows = []
                for _, r in df.iterrows():
                    rows.append(
                        {
                            "obs_id": str(r.get("archivo", "")).replace(".fits", ""),
                            "access_url": str(r["url"]),
                            "mjd": float(r["mjd"]),
                            "detector": str(r["detector"]).split("-")[-1],
                            "collection": str(r.get("coleccion", "spherex_local")),
                        }
                    )
                rows.sort(key=lambda x: x["mjd"])
                return rows
        raise irsa_err

    if len(table) == 0:
        return []

    # Deduplicate by obs_id and sort by t_min (MJD time)
    records: dict[str, dict[str, Any]] = {}
    for r in table:
        obs_id = str(r["obs_id"]).replace("/", "_")
        if obs_id not in records:
            bandpass = str(r.get("energy_bandpassname", ""))
            detector_code = bandpass.split("-")[-1] if "-" in bandpass else bandpass

            records[obs_id] = {
                "obs_id": obs_id,
                "access_url": str(r["access_url"]),
                "mjd": float(r["t_min"]),
                "detector": detector_code,
                "collection": str(r.get("obs_collection", "spherex")),
            }

    sorted_list = sorted(records.values(), key=lambda x: x["mjd"])
    return sorted_list


def select_frames(rows: list[dict[str, Any]], detector: str = "D2", n: int = 16) -> list[dict[str, Any]]:
    """Filters by detector and selects a uniformly distributed sample over the observation timeline."""
    filtered = [r for r in rows if r.get("detector") == detector]
    if not filtered:
        filtered = rows

    if len(filtered) <= n:
        return filtered

    # Uniform temporal sampling (np.linspace) across the entire time series
    indices = np.unique(np.linspace(0, len(filtered) - 1, n).astype(int))
    return [filtered[i] for i in indices]


def _build_cutout_url(access_url: str, ra: float, dec: float, fov: float) -> str:
    """Builds the URL with cutout center and size parameters for IRSA."""
    if "center=" in access_url and "size=" in access_url:
        return access_url
    separator = "&" if "?" in access_url else "?"
    return f"{access_url}{separator}center={ra:.6f},{dec:.6f}d&size={fov:.4f}"


def _find_local_fits(access_url: str) -> Path | None:
    """Checks if the referenced FITS file is already downloaded in RAW_FITS_DIR."""
    clean_name = access_url.split("?")[0].split("/")[-1]
    if not clean_name.endswith(".fits"):
        clean_name += ".fits"

    if settings.RAW_FITS_DIR.is_dir():
        for sub in settings.RAW_FITS_DIR.iterdir():
            if sub.is_dir():
                candidate = sub / clean_name
                if candidate.is_file():
                    return candidate
                # Match by observation ID (e.g., 2025W36_1A_0095_1)
                for f in sub.glob("*.fits"):
                    if f.stem in clean_name:
                        return f
    return None


def fetch_cutout(access_url: str, ra: float, dec: float, fov: float) -> bytes:
    """PURE FETCH: Retrieves raw FITS cutout bytes from disk cache,

    local store, or downloading from IRSA with retries and backoff.
    """
    cutout_key = cache.make_cutout_key(access_url, ra=ra, dec=dec, fov=fov)
    cached_fits_bytes = cache.get_cached_fits(cutout_key)
    if cached_fits_bytes is not None:
        return cached_fits_bytes

    # 1. Check local FITS download store
    local_path = _find_local_fits(access_url)
    if local_path and local_path.is_file():
        try:
            raw_bytes = local_path.read_bytes()
            cache.save_cached_fits(cutout_key, raw_bytes)
            return raw_bytes
        except OSError:
            pass

    # 2. Download cutout from IRSA with retries and exponential backoff
    cutout_url = _build_cutout_url(access_url, ra=ra, dec=dec, fov=fov)
    last_err: Exception | None = None

    for attempt in range(settings.IRSA_MAX_RETRIES):
        try:
            with fits.open(cutout_url, cache=True) as hdul:
                buf = io.BytesIO()
                hdul.writeto(buf)
                raw_bytes = buf.getvalue()
                cache.save_cached_fits(cutout_key, raw_bytes)
                return raw_bytes
        except (
            urllib.error.URLError,
            TimeoutError,
            OSError,
            http.client.IncompleteRead,
            http.client.RemoteDisconnected,
        ) as err:
            last_err = err
            time.sleep(1.5 * (attempt + 1))
        except Exception as err:
            last_err = err
            break

    raise RuntimeError(
        f"Failed to download FITS cutout from IRSA after {settings.IRSA_MAX_RETRIES} attempts: {last_err}"
    )


def aligned_array(fits_bytes: bytes, ra: float, dec: float, fov: float) -> np.ndarray:
    """PURE PROCESSING: Reprojects a FITS cutout onto a north-up grid centered on (ra, dec)

    and subtracts the local sky background. Returns the float array (row 0 = south).
    """
    with fits.open(io.BytesIO(fits_bytes)) as hdul:
        datos = hdul[1].data.astype(float)
        hdr = hdul[1].header.copy()
        wcs_origen = WCS(hdr)

    # 1. Configure target WCS grid centered on target
    npix = max(16, int(fov / SPHEREX_PIXEL_SCALE_DEG))
    destino = WCS(naxis=2)
    destino.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    destino.wcs.crval = [ra, dec]
    destino.wcs.crpix = [npix / 2.0 + 0.5, npix / 2.0 + 0.5]
    destino.wcs.cdelt = [-SPHEREX_PIXEL_SCALE_DEG, SPHEREX_PIXEL_SCALE_DEG]

    # 2. Exact spatial reprojection
    alineado, _ = reproject_interp((datos, wcs_origen), destino, shape_out=(npix, npix))

    # 3. Local sky background subtraction
    sky_bg = np.nanmedian(alineado)
    if not np.isnan(sky_bg):
        alineado -= sky_bg
    return alineado


def _encode_png(norm: np.ndarray, zoom: int) -> bytes:
    """Encodes a 0..1 array (row 0 = south) as a north-up, block-magnified grayscale PNG."""
    img8 = (np.nan_to_num(norm) * 255.0).astype(np.uint8)

    # Flip vertically for standard astronomical orientation (North Up)
    img8 = np.flipud(img8)

    # Nearest-neighbor pixel block magnification for crisp web rendering
    if zoom > 1:
        img8 = np.kron(img8, np.ones((zoom, zoom), dtype=np.uint8))

    buf = io.BytesIO()
    imageio.imwrite(buf, img8, format="PNG")
    return buf.getvalue()


def array_to_png(alineado: np.ndarray, zoom: int = 4) -> bytes:
    """PURE PROCESSING: Percentile contrast stretch (5% to 99.5%) and PNG encoding."""
    lo, hi = np.nanpercentile(alineado, [5.0, 99.5])
    if hi > lo:
        norm = np.clip((alineado - lo) / (hi - lo), 0.0, 1.0)
    else:
        norm = np.zeros_like(alineado)
    return _encode_png(norm, zoom)


def diff_to_png(diff: np.ndarray, zoom: int = 4) -> bytes:
    """PURE PROCESSING: Encodes a difference image symmetrically around zero.

    Gray = no change, white = brighter, black = fainter.
    """
    scale = np.nanpercentile(np.abs(diff), 99.5) if np.isfinite(diff).any() else 0.0
    if scale > 0:
        norm = 0.5 + 0.5 * np.clip(diff / scale, -1.0, 1.0)
    else:
        norm = np.full_like(diff, 0.5)
    # NaN pixels (e.g. masked or saturated) show as "no change".
    return _encode_png(np.where(np.isnan(norm), 0.5, norm), zoom)


def png_data_uri(png_bytes: bytes) -> str:
    """Wraps PNG bytes as a data URI usable directly as an <img> src."""
    return "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")


def cutout_to_png(
    fits_bytes: bytes,
    ra: float,
    dec: float,
    fov: float,
    zoom: int = 4,
) -> bytes:
    """PURE PROCESSING: Converts in-memory FITS bytes to an aligned, contrast-stretched PNG image."""
    return array_to_png(aligned_array(fits_bytes, ra=ra, dec=dec, fov=fov), zoom=zoom)


def cutout_wavelength(fits_bytes: bytes | fits.Header, ra: float, dec: float, fobj: Any = None) -> float | None:
    """Extracts observed wavelength in micrometers at position (ra, dec)

    from the FITS WCS 'W' key in memory or header.
    """
    try:
        if isinstance(fits_bytes, fits.Header):
            hdr = fits_bytes
            hdul = fobj
        else:
            hdul = fits.open(io.BytesIO(fits_bytes))
            hdr = hdul[1].header

        w_spatial = WCS(hdr)
        coord = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame="icrs")
        x, y = w_spatial.world_to_pixel(coord)

        sw = WCS(hdr, fobj=hdul, key="W")
        sw.sip = None
        lam, _ = sw.pixel_to_world(x, y)
        return round(float(lam.to(u.micrometer).value), 4)
    except Exception:
        return None


# Alias for backwards compatibility
extract_wavelength = cutout_wavelength


def frame_png(
    access_url: str,
    ra: float,
    dec: float,
    fov: float,
    zoom: int = 4,
) -> bytes:
    """High-level helper: fetches/downloads FITS cutout and processes it into PNG."""
    raw_fits = fetch_cutout(access_url, ra=ra, dec=dec, fov=fov)
    return cutout_to_png(raw_fits, ra=ra, dec=dec, fov=fov, zoom=zoom)


def build_epochs(frames: list[dict[str, Any]], threshold_days: float = 45.0) -> list[dict[str, Any]]:
    """Clusters a sequence of frames into astronomical observation epochs

    based on SPHEREx survey timeline gaps.
    """
    if not frames:
        return []

    # Ensure chronological order by MJD
    sorted_frames = sorted(frames, key=lambda f: float(f["mjd"]))

    epochs: list[list[dict[str, Any]]] = []
    current_cluster: list[dict[str, Any]] = [sorted_frames[0]]

    for f in sorted_frames[1:]:
        prev_mjd = float(current_cluster[-1]["mjd"])
        curr_mjd = float(f["mjd"])
        if (curr_mjd - prev_mjd) > threshold_days:
            epochs.append(current_cluster)
            current_cluster = [f]
        else:
            current_cluster.append(f)
    epochs.append(current_cluster)

    result: list[dict[str, Any]] = []
    for idx, cluster in enumerate(epochs, start=1):
        mjds = [float(f["mjd"]) for f in cluster]
        mjd_min = min(mjds)
        mjd_max = max(mjds)
        mjd_mean = sum(mjds) / len(mjds)

        start_date = _mjd_to_iso_date(mjd_min)
        end_date = _mjd_to_iso_date(mjd_max)
        detector = cluster[0].get("detector", "D2")

        # Generate descriptive label
        start_month_year = datetime.fromisoformat(start_date).strftime("%b %Y")
        label = f"Epoch {idx} ({start_month_year})"

        result.append(
            {
                "epoch_index": idx,
                "label": label,
                "mjd_start": round(mjd_min, 3),
                "mjd_end": round(mjd_max, 3),
                "mjd_mean": round(mjd_mean, 3),
                "start_date": start_date,
                "end_date": end_date,
                "frame_count": len(cluster),
                "detector": detector,
                "frames": cluster,
            }
        )

    return result


def spectrum_points(
    frames: list[dict[str, Any]],
    ra: float,
    dec: float,
    aperture_radius_pixels: int = SPECTRUM_APERTURE_RADIUS_PIXELS,
) -> list[dict[str, Any]]:
    """Calculates aperture photometry and spectral points (flux vs wavelength)

    for each observation at the target position.
    """
    points: list[dict[str, Any]] = []

    for f in frames:
        access_url = f.get("access_url") or f.get("url")
        if not access_url:
            continue

        try:
            # Fetch FITS (from disk cache or download)
            fits_bytes = fetch_cutout(access_url, ra=ra, dec=dec, fov=settings.DEFAULT_FOV)
            with fits.open(io.BytesIO(fits_bytes)) as hdul:
                data = hdul[1].data.astype(float)
                hdr = hdul[1].header
                w_spatial = WCS(hdr)

                # Target pixel coordinates
                coord = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame="icrs")
                px, py = w_spatial.world_to_pixel(coord)
                ix, iy = int(np.round(float(px))), int(np.round(float(py)))

                h, w = data.shape
                # Square aperture around target
                r = aperture_radius_pixels
                y0, y1 = max(0, iy - r), min(h, iy + r + 1)
                x0, x1 = max(0, ix - r), min(w, ix + r + 1)

                aperture_data = data[y0:y1, x0:x1]
                sky_bg = float(np.nanmedian(data))
                # Surface brightness (MJy/sr) summed over pixels -> flux in mJy
                to_mjy = SPHEREX_PIXEL_SR * 1e9
                flux_val = float(np.nansum(aperture_data - sky_bg)) * to_mjy

                # Estimate uncertainty as background std dev * sqrt(area)
                sky_std = float(np.nanstd(data))
                area = aperture_data.size
                flux_err = float(sky_std * math.sqrt(area)) * to_mjy if area > 0 else None

            # Wavelength
            lam = f.get("wavelength_um")
            if lam is None:
                lam = cutout_wavelength(fits_bytes, ra=ra, dec=dec)

            if lam is not None:
                points.append(
                    {
                        "wavelength_um": float(lam),
                        "flux": round(flux_val, 4),
                        "flux_err": round(flux_err, 4) if flux_err else None,
                        "mjd": round(float(f["mjd"]), 3),
                        "date": str(f.get("date", _mjd_to_iso_date(float(f["mjd"])))),
                        "detector": str(f.get("detector", "D2")),
                        "obs_id": f.get("obs_id"),
                    }
                )
        except Exception:
            continue

    # Sort by ascending wavelength
    points.sort(key=lambda p: p["wavelength_um"])
    return points