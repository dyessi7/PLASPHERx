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

# Semáforo para controlar descargas simultáneas hacia IRSA y proteger contra bloqueos (429)
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
    """Helper que resuelve el objetivo, aplica movimiento propio si aplica

    y valida las coordenadas.
    Retorna (name, ra, dec, fov, target_id).
    """
    if target:
        target_info = targets.get_target_by_id(target, apply_pm=True)
        if not target_info:
            raise HTTPException(
                status_code=404,
                detail=f"Objetivo '{target}' no encontrado en el catálogo. Consulte /api/targets.",
            )
        resolved_ra = target_info.ra
        resolved_dec = target_info.dec
        resolved_fov = fov if fov is not None else target_info.fov
        return target_info.name, resolved_ra, resolved_dec, resolved_fov, target_info.id

    if ra is None or dec is None:
        raise HTTPException(
            status_code=400,
            detail="Debe proporcionar el parámetro 'target' o bien las coordenadas ('ra' y 'dec').",
        )

    resolved_fov = fov if fov is not None else settings.DEFAULT_FOV
    matched = targets.find_target_by_coords(ra, dec, tolerance_deg=0.05)
    name = matched.name if matched else f"custom_{ra:.4f}_{dec:.4f}"
    target_id = matched.id if matched else "custom"
    return name, ra, dec, resolved_fov, target_id


@app.get(
    "/api/health",
    response_model=HealthResponse,
    summary="Verificación de estado del servicio",
    tags=["Sistema"],
)
def health_check():
    """Verifica la conectividad, el estado del servidor y las estadísticas de caché en disco."""
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
    summary="Catálogo de los 5 objetivos predefinidos",
    tags=["Catálogo"],
)
def get_targets():
    """Devuelve el catálogo de los 5 objetivos predefinidos con sus coordenadas base y tipo (variable o mover)."""
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
    summary="Secuencia temporal de cuadros para un objetivo o coordenadas",
    tags=["Astronomía"],
)
def get_frames(
    request: Request,
    target: str | None = Query(None, description="ID del objetivo predefinido (ej: 'r_dra', 'barnard')"),
    ra: float | None = Query(None, ge=0.0, le=360.0, description="Ascensión Recta en grados (0 a 360)"),
    dec: float | None = Query(None, ge=-90.0, le=90.0, description="Declinación en grados (-90 a 90)"),
    fov: float | None = Query(None, ge=0.02, le=0.5, description="Campo de visión en grados (0.02 a 0.5)"),
    detector: str = Query(settings.DEFAULT_DETECTOR, description="Detector SPHEREx (D1 a D6)"),
    n: int = Query(16, ge=1, le=settings.MAX_FRAMES, description="Número máximo de cuadros (1 a 24)"),
):
    if detector not in settings.ALLOWED_DETECTORS:
        raise HTTPException(
            status_code=400,
            detail=f"Parámetro 'detector' inválido. Debe ser uno de {', '.join(settings.ALLOWED_DETECTORS)}.",
        )

    name, target_ra, target_dec, target_fov, _ = _resolve_target_and_coordinates(target, ra, dec, fov)

    # 1. Comprobar caché de metadatos SIA
    query_key = cache.make_query_key(
        ra=target_ra, dec=target_dec, fov=target_fov, detector=detector, n=n
    )
    cached_payload = cache.get_cached_metadata(query_key)
    if cached_payload is not None:
        return cached_payload

    # 2. Consultar catálogo de imágenes en IRSA
    try:
        rows = spherex.search_images(ra=target_ra, dec=target_dec)
        selected = spherex.select_frames(rows=rows, detector=detector, n=n)
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Tiempo de espera agotado al consultar IRSA.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Fallo al recuperar metadatos de IRSA: {exc}")

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

    # Guardar metadatos en caché
    cache.save_cached_metadata(query_key, response_data.model_dump())
    return response_data


@app.get(
    "/api/frame",
    responses={
        200: {"content": {"image/png": {}}, "description": "Imagen recortada y alineada en PNG"},
        400: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
    summary="Descarga y procesa al vuelo el recorte PNG alineado",
    tags=["Astronomía"],
)
def get_frame(
    src: str = Query(..., description="URL oficial del archivo FITS en IRSA"),
    ra: float = Query(..., ge=0.0, le=360.0, description="Ascensión Recta en grados"),
    dec: float = Query(..., ge=-90.0, le=90.0, description="Declinación en grados"),
    fov: float = Query(settings.DEFAULT_FOV, ge=0.02, le=0.5, description="Campo de visión"),
):
    """Sirve el PNG procesado y alineado:

    1. Busca primero en la caché de disco (PNG).
    2. Si no existe, descarga el FITS con `fetch_cutout` (usando caché FITS y semáforo de conexión).
    3. Procesa y alinea en memoria con `cutout_to_png`.
    4. Guarda el resultado en caché y lo entrega como imagen PNG.
    """
    if not src.startswith(settings.IRSA_PREFIX):
        raise HTTPException(
            status_code=400,
            detail=f"URL 'src' inválida. Únicamente se permiten URLs oficiales de {settings.IRSA_PREFIX}.",
        )

    # 1. Comprobar caché de imagen PNG
    cache_key = cache.make_frame_key(src=src, ra=ra, dec=dec, fov=fov)
    cached_bytes = cache.get_cached_frame(cache_key)
    if cached_bytes is not None:
        return Response(
            content=cached_bytes,
            media_type="image/png",
            headers={"Cache-Control": f"public, max-age={settings.FRAME_CACHE_MAX_AGE_SECONDS}"},
        )

    # 2. Descargar y procesar al vuelo
    try:
        with _irsa_download_semaphore:
            fits_bytes = spherex.fetch_cutout(access_url=src, ra=ra, dec=dec, fov=fov)
            png_bytes = spherex.cutout_to_png(fits_bytes, ra=ra, dec=dec, fov=fov, zoom=4)
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Tiempo de espera agotado al descargar recorte de IRSA.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Fallo al procesar recorte de IRSA: {exc}")

    # Guardar PNG en caché
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
    summary="Agrupación temporal de observaciones por épocas de SPHEREx",
    tags=["Vistas Avanzadas"],
)
def get_epochs(
    request: Request,
    target: str | None = Query(None, description="ID del objetivo predefinido (ej: 'r_dra')"),
    ra: float | None = Query(None, ge=0.0, le=360.0, description="Ascensión Recta en grados"),
    dec: float | None = Query(None, ge=-90.0, le=90.0, description="Declinación en grados"),
    fov: float | None = Query(None, ge=0.02, le=0.5, description="Campo de visión en grados"),
    detector: str = Query(settings.DEFAULT_DETECTOR, description="Detector SPHEREx (D1 a D6)"),
    threshold_days: float = Query(
        45.0, ge=5.0, le=180.0, description="Umbral de días para separar épocas (default: 45 días)"
    ),
):
    """Consume `build_epochs` para agrupar los cuadros en pasadas y épocas de exploración."""
    if detector not in settings.ALLOWED_DETECTORS:
        raise HTTPException(
            status_code=400,
            detail=f"Parámetro 'detector' inválido. Debe ser uno de {', '.join(settings.ALLOWED_DETECTORS)}.",
        )

    name, target_ra, target_dec, target_fov, _ = _resolve_target_and_coordinates(target, ra, dec, fov)

    try:
        rows = spherex.search_images(ra=target_ra, dec=target_dec)
        selected = spherex.select_frames(rows=rows, detector=detector, n=settings.MAX_FRAMES)
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Tiempo de espera agotado al consultar IRSA.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Fallo al consultar IRSA: {exc}")

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
    summary="Puntos de fotometría y espectro (flujo vs longitud de onda)",
    tags=["Vistas Avanzadas"],
)
def get_spectrum(
    target: str | None = Query(None, description="ID del objetivo predefinido (ej: 'rw_aur')"),
    ra: float | None = Query(None, ge=0.0, le=360.0, description="Ascensión Recta en grados"),
    dec: float | None = Query(None, ge=-90.0, le=90.0, description="Declinación en grados"),
    fov: float | None = Query(None, ge=0.02, le=0.5, description="Campo de visión en grados"),
    detector: str = Query(settings.DEFAULT_DETECTOR, description="Detector SPHEREx (D1 a D6)"),
    n: int = Query(16, ge=1, le=settings.MAX_FRAMES, description="Número de puntos a analizar"),
):
    """Consume `spectrum_points` para calcular el flujo fotométrico

    y la longitud de onda de cada observación en el objetivo.
    """
    if detector not in settings.ALLOWED_DETECTORS:
        raise HTTPException(
            status_code=400,
            detail=f"Parámetro 'detector' inválido. Debe ser uno de {', '.join(settings.ALLOWED_DETECTORS)}.",
        )

    name, target_ra, target_dec, target_fov, _ = _resolve_target_and_coordinates(target, ra, dec, fov)

    try:
        rows = spherex.search_images(ra=target_ra, dec=target_dec)
        selected = spherex.select_frames(rows=rows, detector=detector, n=n)
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Tiempo de espera agotado al consultar IRSA.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Fallo al consultar IRSA: {exc}")

    # Extraer puntos fotométricos y espectrales
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
