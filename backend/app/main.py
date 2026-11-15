import threading
from datetime import datetime, timezone
from urllib.parse import quote
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import cache, spherex, targets
from app.config import get_settings
from app.schemas import (
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
)

# Semaphore to control concurrent downloads to IRSA and prevent rate-limiting (429)
_irsa_download_semaphore = threading.Semaphore(settings.MAX_CONCURRENT_DOWNLOADS)


@app.exception_handler(HTTPException)
def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": str(exc.detail)},
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
                status_code=404,
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
        404: {"model": ErrorResponse},
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
    cached_bytes = cache.get_cached_frame(cache_key)
    if cached_bytes is not None:
        return Response(
            content=cached_bytes,
            media_type="image/png",
            headers={"Cache-Control": f"public, max-age={settings.FRAME_CACHE_MAX_AGE_SECONDS}"},
        )

    # 2. Fetch and process cutout on the fly
    try:
        with _irsa_download_semaphore:
            fits_bytes = spherex.fetch_cutout(access_url=src, ra=ra, dec=dec, fov=fov)
            png_bytes = spherex.cutout_to_png(fits_bytes, ra=ra, dec=dec, fov=fov, zoom=4)
    except TimeoutError:
        raise HTTPException(status_code=504, detail="IRSA cutout download timed out.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to process cutout from IRSA: {exc}")

    # Save PNG to cache
    cache.save_cached_frame(cache_key, png_bytes)

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": f"public, max-age={settings.FRAME_CACHE_MAX_AGE_SECONDS}"},
    )


@app.get(
    "/api/epochs",
    response_model=EpochsResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
    summary="Temporal grouping of observations by SPHEREx survey epochs",
    tags=["Advanced Views"],
)
def get_epochs(
    request: Request,
    target: str | None = Query(None, description="Canonical ID of the predefined target (e.g., 'r_dra')"),
    ra: float | None = Query(None, ge=0.0, le=360.0, description="Right Ascension in degrees"),
    dec: float | None = Query(None, ge=-90.0, le=90.0, description="Declination in degrees"),
    fov: float | None = Query(None, ge=0.02, le=0.5, description="Field of view in degrees"),
    detector: str = Query(settings.DEFAULT_DETECTOR, description="SPHEREx detector identifier (D1 to D6)"),
    threshold_days: float = Query(
        45.0, ge=5.0, le=180.0, description="Day separation threshold to distinguish survey epochs (default: 45 days)"
    ),
):
    """Consumes build_epochs to cluster observation frames into survey passes and observation epochs."""
    if detector not in settings.ALLOWED_DETECTORS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid 'detector' parameter. Must be one of {', '.join(settings.ALLOWED_DETECTORS)}.",
        )

    name, target_ra, target_dec, target_fov, _ = _resolve_target_and_coordinates(target, ra, dec, fov)

    try:
        rows = spherex.search_images(ra=target_ra, dec=target_dec)
        selected = spherex.select_frames(rows=rows, detector=detector, n=settings.MAX_FRAMES)
    except TimeoutError:
        raise HTTPException(status_code=504, detail="IRSA observation query timed out.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to query IRSA: {exc}")

    base_url = str(request.base_url).rstrip("/")
    frames_list = []
    for row in selected:
        encoded_src = quote(row["access_url"], safe="")
        frame_url = (
            f"{base_url}/api/frame?src={encoded_src}&ra={target_ra}&dec={target_dec}&fov={target_fov}"
        )
        frames_list.append(
            {
                "url": frame_url,
                "mjd": row["mjd"],
                "date": _mjd_to_iso_date(row["mjd"]),
                "detector": row["detector"],
                "wavelength_um": None,
                "obs_id": row.get("obs_id"),
            }
        )

    raw_epochs = spherex.build_epochs(frames_list, threshold_days=threshold_days)

    epoch_items = [
        EpochItem(
            epoch_index=e["epoch_index"],
            label=e["label"],
            mjd_start=e["mjd_start"],
            mjd_end=e["mjd_end"],
            mjd_mean=e["mjd_mean"],
            start_date=e["start_date"],
            end_date=e["end_date"],
            frame_count=e["frame_count"],
            detector=e["detector"],
            frames=[FrameItem(**f) for f in e["frames"]],
        )
        for e in raw_epochs
    ]

    return EpochsResponse(
        target=TargetBase(
            name=name,
            ra=target_ra,
            dec=target_dec,
            fov=target_fov,
        ),
        detector=detector,
        total_epochs=len(epoch_items),
        epochs=epoch_items,
    )


@app.get(
    "/api/spectrum",
    response_model=SpectrumResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
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
    n: int = Query(16, ge=1, le=settings.MAX_FRAMES, description="Maximum number of observation points to analyze"),
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
    raw_points = spherex.spectrum_points(selected, ra=target_ra, dec=target_dec)

    spectrum_items = [SpectrumPoint(**p) for p in raw_points]

    return SpectrumResponse(
        target=TargetBase(
            name=name,
            ra=target_ra,
            dec=target_dec,
            fov=target_fov,
        ),
        detector=detector,
        total_points=len(spectrum_items),
        points=spectrum_items,
    )
