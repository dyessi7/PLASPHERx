import warnings

import numpy as np
from datetime import datetime, timezone
from urllib.parse import parse_qs, quote, urlparse
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app import cache, spherex, targets
from app.config import get_settings
from app.schemas import (
    DiffItem,
    EpochItem,
    EpochsResponse,
    ErrorResponse,
    FrameItem,
    FramesResponse,
    HealthResponse,
    SpectrumPoint,
    SpectrumResponse,
    TargetBase,
    TargetsListResponse,
)

settings = get_settings()

app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description=settings.API_DESCRIPTION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=settings.ALLOWED_METHODS,
    allow_headers=["*"],
    # Lets the browser read the wavelength header on /api/frame responses.
    expose_headers=["X-Wavelength-Um"],
)

@app.exception_handler(HTTPException)
def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": str(exc.detail)},
    )


@app.exception_handler(RequestValidationError)
def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={"error": "Invalid request parameters."},
    )


def _mjd_to_iso_date(mjd: float) -> str:
    unix_seconds = (mjd - 40587.0) * 86400.0
    return datetime.fromtimestamp(unix_seconds, tz=timezone.utc).strftime("%Y-%m-%d")


def _resolve_target_and_coordinates(
    target: str | None,
    ra: float | None,
    dec: float | None,
    fov: float | None,
) -> tuple[str, float, float, float, str]:
    """Helper that resolves target metadata, applies proper motion if applicable,

    and validates coordinates.
    Returns (name, ra, dec, fov, target_id).
    """
    if target:
        target_info = targets.get_target_by_id(target, apply_pm=True)
        if not target_info:
            raise HTTPException(
                status_code=400,
                detail=f"Target '{target}' not found in catalog. See /api/targets.",
            )
        resolved_ra = target_info.ra
        resolved_dec = target_info.dec
        resolved_fov = fov if fov is not None else target_info.fov
        return target_info.name, resolved_ra, resolved_dec, resolved_fov, target_info.id

    if ra is None or dec is None:
        raise HTTPException(
            status_code=400,
            detail="Must provide either 'target' parameter or both coordinates ('ra' and 'dec').",
        )

    resolved_fov = fov if fov is not None else settings.DEFAULT_FOV
    matched = targets.find_target_by_coords(ra, dec, tolerance_deg=0.05)
    name = matched.name if matched else f"custom_{ra:.4f}_{dec:.4f}"
    target_id = matched.id if matched else "custom"
    return name, ra, dec, resolved_fov, target_id


def _select_rows_cached(ra: float, dec: float, fov: float, detector: str, n: int) -> list[dict]:
    """Frame rows for a query, reusing the /api/frames metadata cache when present

    so follow-up requests do not depend on IRSA being reachable again.
    """
    cached = cache.get_cached_metadata(
        cache.make_query_key(ra=ra, dec=dec, fov=fov, detector=detector, n=n)
    )
    if cached and cached.get("frames"):
        rows = []
        for f in cached["frames"]:
            src = parse_qs(urlparse(f["url"]).query).get("src", [None])[0]
            if src:
                rows.append({"access_url": src, "mjd": f["mjd"], "detector": f["detector"]})
        if rows:
            return rows

    rows = spherex.search_images(ra=ra, dec=dec)
    return spherex.select_frames(rows=rows, detector=detector, n=n)


@app.get(
    "/api/health",
    response_model=HealthResponse,
    summary="Service health verification",
    tags=["System"],
)
def health_check():
    """Verifies system connectivity, server operational status, and disk cache statistics."""
    return HealthResponse(
        status="ok",
        version=settings.API_VERSION,
        cache_dir=str(settings.CACHE_DIR),
        cache_writable=cache.is_cache_writable(),
        cache_stats=cache.get_cache_stats(),
    )


@app.get(
    "/api/targets",
    response_model=TargetsListResponse,
    summary="Catalog of the 5 predefined targets",
    tags=["Catalog"],
)
def get_targets():
    """Returns the catalog of the 5 predefined targets with their base coordinates and category ('variable' or 'mover')."""
    catalog_targets = targets.list_targets(apply_pm=False)
    return TargetsListResponse(targets=catalog_targets, total=len(catalog_targets))


@app.get(
    "/api/frames",
    response_model=FramesResponse,
    responses={
        400: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
    summary="Temporal sequence of frames for a target or coordinates",
    tags=["Astronomy"],
)
def get_frames(
    request: Request,
    target: str | None = Query(None, description="Canonical ID of the predefined target (e.g., 'r_dra', 'barnard')"),
    ra: float | None = Query(None, ge=0.0, le=360.0, description="Right Ascension in degrees (0 to 360)"),
    dec: float | None = Query(None, ge=-90.0, le=90.0, description="Declination in degrees (-90 to 90)"),
    fov: float | None = Query(None, ge=0.02, le=0.5, description="Field of view in degrees (0.02 to 0.5)"),
    detector: str = Query(settings.DEFAULT_DETECTOR, description="SPHEREx detector identifier (D1 to D6)"),
    n: int = Query(16, ge=1, le=settings.MAX_FRAMES, description="Maximum number of frames (1 to 24)"),
):
    if detector not in settings.ALLOWED_DETECTORS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid 'detector' parameter. Must be one of {', '.join(settings.ALLOWED_DETECTORS)}.",
        )

    name, target_ra, target_dec, target_fov, _ = _resolve_target_and_coordinates(target, ra, dec, fov)

    # 1. Check SIA metadata cache
    query_key = cache.make_query_key(
        ra=target_ra, dec=target_dec, fov=target_fov, detector=detector, n=n
    )
    cached_payload = cache.get_cached_metadata(query_key)
    if cached_payload is not None:
        return cached_payload

    # 2. Query IRSA image catalog
    try:
        rows = spherex.search_images(ra=target_ra, dec=target_dec)
        selected = spherex.select_frames(rows=rows, detector=detector, n=n)
    except TimeoutError:
        raise HTTPException(status_code=504, detail="IRSA metadata query timed out.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to retrieve metadata from IRSA: {exc}")

    base_url = str(request.base_url).rstrip("/")
    frames_payload: list[FrameItem] = []

    for row in selected:
        access_url = row["access_url"]
        encoded_src = quote(access_url, safe="")
        frame_url = (
            f"{base_url}/api/frame?src={encoded_src}&ra={target_ra}&dec={target_dec}&fov={target_fov}"
        )
        frames_payload.append(
            FrameItem(
                url=frame_url,
                mjd=row["mjd"],
                date=_mjd_to_iso_date(row["mjd"]),
                detector=row["detector"],
                wavelength_um=None,
                obs_id=row.get("obs_id"),
            )
        )

    response_data = FramesResponse(
        target=TargetBase(
            name=name,
            ra=target_ra,
            dec=target_dec,
            fov=target_fov,
        ),
        frames=frames_payload,
        total_frames=len(frames_payload),
        source="irsa",
    )

    # Save metadata to cache
    cache.save_cached_metadata(query_key, response_data.model_dump())
    return response_data


@app.get(
    "/api/frame",
    responses={
        200: {"content": {"image/png": {}}, "description": "Cropped and aligned PNG image"},
        400: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
    summary="On-the-fly cutout download, alignment, and PNG generation",
    tags=["Astronomy"],
)
def get_frame(
    src: str = Query(..., description="Official FITS cutout URL from IRSA"),
    ra: float = Query(..., ge=0.0, le=360.0, description="Right Ascension in degrees"),
    dec: float = Query(..., ge=-90.0, le=90.0, description="Declination in degrees"),
    fov: float = Query(settings.DEFAULT_FOV, ge=0.02, le=0.5, description="Field of view in degrees"),
):
    """Serves the processed and aligned PNG frame:

    1. Checks the disk cache first for existing PNG.
    2. If not found, downloads the FITS cutout with fetch_cutout (using cache & semaphore).
    3. Processes and aligns in memory with cutout_to_png.
    4. Saves the resulting PNG to disk cache and returns the image response.
    """
    if not src.startswith(settings.IRSA_PREFIX):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid 'src' URL. Only official URLs starting with {settings.IRSA_PREFIX} are allowed.",
        )

    # 1. Check PNG frame cache
    cache_key = cache.make_frame_key(src=src, ra=ra, dec=dec, fov=fov)
    png_bytes = cache.get_cached_frame(cache_key)

    if png_bytes is not None:
        # The FITS is only needed for the wavelength header; never re-download it for that.
        fits_bytes = cache.get_cached_fits(cache.make_cutout_key(src, ra=ra, dec=dec, fov=fov))
    else:
        # 2. Fetch and process cutout on the fly
        try:
            fits_bytes = spherex.fetch_cutout(access_url=src, ra=ra, dec=dec, fov=fov)
            png_bytes = spherex.cutout_to_png(fits_bytes, ra=ra, dec=dec, fov=fov, zoom=4)
        except TimeoutError:
            raise HTTPException(status_code=504, detail="IRSA cutout download timed out.")
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Failed to process cutout from IRSA: {exc}")

        # Save PNG to cache
        cache.save_cached_frame(cache_key, png_bytes)

    headers = {"Cache-Control": f"public, max-age={settings.FRAME_CACHE_MAX_AGE_SECONDS}"}
    wavelength = spherex.cutout_wavelength(fits_bytes, ra=ra, dec=dec) if fits_bytes else None
    if wavelength is not None:
        headers["X-Wavelength-Um"] = str(wavelength)

    return Response(content=png_bytes, media_type="image/png", headers=headers)


@app.get(
    "/api/epochs",
    response_model=EpochsResponse,
    responses={
        400: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
    summary="Temporal grouping of observations by SPHEREx survey epochs",
    tags=["Advanced Views"],
)
def get_epochs(
    target: str | None = Query(None, description="Canonical ID of the predefined target (e.g., 'r_dra')"),
    ra: float | None = Query(None, ge=0.0, le=360.0, description="Right Ascension in degrees"),
    dec: float | None = Query(None, ge=-90.0, le=90.0, description="Declination in degrees"),
    fov: float | None = Query(None, ge=0.02, le=0.5, description="Field of view in degrees"),
    detector: str = Query(settings.DEFAULT_DETECTOR, description="SPHEREx detector identifier (D1 to D6)"),
    n: int = Query(16, ge=1, le=settings.MAX_FRAMES, description="Frames to sample (same as /api/frames, so cutouts are cached)"),
    threshold_days: float = Query(
        45.0, ge=5.0, le=180.0, description="Day separation threshold to distinguish survey epochs (default: 45 days)"
    ),
):
    """Groups the frames into observing epochs, stacks each epoch into one image,
    and returns the differences between consecutive epochs. Images are PNG data URIs.
    """
    if detector not in settings.ALLOWED_DETECTORS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid 'detector' parameter. Must be one of {', '.join(settings.ALLOWED_DETECTORS)}.",
        )

    name, target_ra, target_dec, target_fov, _ = _resolve_target_and_coordinates(target, ra, dec, fov)

    try:
        selected = _select_rows_cached(target_ra, target_dec, target_fov, detector, n)
    except TimeoutError:
        raise HTTPException(status_code=504, detail="IRSA observation query timed out.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to query IRSA: {exc}")

    # Aligned arrays for every frame; frames that fail to download are skipped.
    frames_list = []
    for row in selected:
        try:
            fits_bytes = spherex.fetch_cutout(
                access_url=row["access_url"], ra=target_ra, dec=target_dec, fov=target_fov
            )
            array = spherex.aligned_array(fits_bytes, ra=target_ra, dec=target_dec, fov=target_fov)
        except TimeoutError:
            raise HTTPException(status_code=504, detail="IRSA cutout download timed out.")
        except Exception:
            continue
        frames_list.append({"mjd": row["mjd"], "detector": row["detector"], "array": array})

    if not frames_list:
        raise HTTPException(status_code=502, detail="None of the frames could be retrieved from IRSA.")

    epoch_items: list[EpochItem] = []
    stacks: list[np.ndarray] = []
    for e in spherex.build_epochs(frames_list, threshold_days=threshold_days):
        with warnings.catch_warnings():
            # Pixels that are NaN in every frame stay NaN; that is expected.
            warnings.simplefilter("ignore", RuntimeWarning)
            stack = np.nanmean(np.stack([f["array"] for f in e["frames"]]), axis=0)
        stacks.append(stack)
        epoch_items.append(
            EpochItem(
                id=f"e{e['epoch_index']}",
                url=spherex.png_data_uri(spherex.array_to_png(stack, zoom=4)),
                date_start=e["start_date"],
                date_end=e["end_date"],
                mjd_mid=e["mjd_mean"],
                n_frames=e["frame_count"],
            )
        )

    diff_items = [
        DiffItem(
            url=spherex.png_data_uri(spherex.diff_to_png(stacks[i] - stacks[i - 1], zoom=4)),
            a=epoch_items[i - 1].id,
            b=epoch_items[i].id,
        )
        for i in range(1, len(stacks))
    ]

    return EpochsResponse(
        target=TargetBase(
            name=name,
            ra=target_ra,
            dec=target_dec,
            fov=target_fov,
        ),
        detector=detector,
        epochs=epoch_items,
        diffs=diff_items,
    )


@app.get(
    "/api/spectrum",
    response_model=SpectrumResponse,
    responses={
        400: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
    summary="Photometry and spectral points (flux vs wavelength)",
    tags=["Advanced Views"],
)
def get_spectrum(
    target: str | None = Query(None, description="Canonical ID of the predefined target (e.g., 'rw_aur')"),
    ra: float | None = Query(None, ge=0.0, le=360.0, description="Right Ascension in degrees"),
    dec: float | None = Query(None, ge=-90.0, le=90.0, description="Declination in degrees"),
    fov: float | None = Query(None, ge=0.02, le=0.5, description="Field of view in degrees"),
    detector: str = Query(settings.DEFAULT_DETECTOR, description="SPHEREx detector identifier (D1 to D6)"),
    n: int = Query(4, ge=1, le=settings.MAX_FRAMES, description="Maximum number of observation points to analyze"),
):
    """Consumes spectrum_points to calculate aperture photometry and wavelength for each observation at the target."""
    if detector not in settings.ALLOWED_DETECTORS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid 'detector' parameter. Must be one of {', '.join(settings.ALLOWED_DETECTORS)}.",
        )

    name, target_ra, target_dec, target_fov, _ = _resolve_target_and_coordinates(target, ra, dec, fov)

    try:
        rows = spherex.search_images(ra=target_ra, dec=target_dec)
        selected = spherex.select_frames(rows=rows, detector=detector, n=n)
    except TimeoutError:
        raise HTTPException(status_code=504, detail="IRSA observation query timed out.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to query IRSA: {exc}")

    # Extract photometric and spectral points
    try:
        raw_points = spherex.spectrum_points(
            selected, ra=target_ra, dec=target_dec, fov=target_fov
        )
    except TimeoutError:
        raise HTTPException(status_code=504, detail="IRSA cutout download timed out.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to calculate spectrum: {exc}")

    spectrum_items = [SpectrumPoint(**p) for p in raw_points]

    return SpectrumResponse(
        target=TargetBase(
            name=name,
            ra=target_ra,
            dec=target_dec,
            fov=target_fov,
        ),
        detector=detector,
        flux_unit=spherex.SPECTRUM_FLUX_UNIT,
        aperture_arcsec=(2 * spherex.SPECTRUM_APERTURE_RADIUS_PIXELS + 1) * spherex.SPHEREX_PIXEL_SCALE_ARCSEC,
        total_points=len(spectrum_items),
        points=spectrum_items,
    )