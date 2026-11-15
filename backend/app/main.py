from datetime import datetime, timezone
from urllib.parse import quote
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import cache, spherex

app = FastAPI(title="SPHEREx Sky Viewer API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

ALLOWED_DETECTORS = {"D1", "D2", "D3", "D4", "D5", "D6"}
IRSA_PREFIX = "https://irsa.ipac.caltech.edu/"


@app.exception_handler(HTTPException)
def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": str(exc.detail)},
    )


def _mjd_to_iso_date(mjd: float) -> str:
    unix_seconds = (mjd - 40587.0) * 86400.0
    return datetime.fromtimestamp(unix_seconds, tz=timezone.utc).strftime("%Y-%m-%d")


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/frames")
def get_frames(
    request: Request,
    ra: float = Query(..., description="Right Ascension in degrees (0 to 360)"),
    dec: float = Query(..., description="Declination in degrees (-90 to 90)"),
    fov: float = Query(0.1, description="Field of view in degrees (0.02 to 0.5)"),
    detector: str = Query("D2", description="Detector identifier (D1 to D6)"),
    n: int = Query(16, description="Maximum number of frames (1 to 24)"),
):
    if not (0.0 <= ra <= 360.0):
        raise HTTPException(status_code=400, detail="Parameter 'ra' must be between 0 and 360.")
    if not (-90.0 <= dec <= 90.0):
        raise HTTPException(status_code=400, detail="Parameter 'dec' must be between -90 and 90.")
    if not (0.02 <= fov <= 0.5):
        raise HTTPException(status_code=400, detail="Parameter 'fov' must be between 0.02 and 0.5.")
    if detector not in ALLOWED_DETECTORS:
        raise HTTPException(status_code=400, detail="Parameter 'detector' must be one of D1..D6.")
    if not (1 <= n <= 24):
        raise HTTPException(status_code=400, detail="Parameter 'n' must be between 1 and 24.")

    try:
        rows = spherex.search_images(ra=ra, dec=dec)
        selected = spherex.select_frames(rows=rows, detector=detector, n=n)
    except TimeoutError:
        raise HTTPException(status_code=504, detail="IRSA search request timed out.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to retrieve metadata from IRSA: {exc}")

    base_url = str(request.base_url).rstrip("/")
    frames_payload = []

    for row in selected:
        encoded_src = quote(row["access_url"], safe="")
        frame_url = f"{base_url}/api/frame?src={encoded_src}&ra={ra}&dec={dec}&fov={fov}"
        frames_payload.append(
            {
                "url": frame_url,
                "mjd": row["mjd"],
                "date": _mjd_to_iso_date(row["mjd"]),
                "detector": row["detector"],
                "wavelength_um": None,
            }
        )

    return {
        "target": {
            "name": f"custom_{ra:.4f}_{dec:.4f}",
            "ra": ra,
            "dec": dec,
            "fov": fov,
        },
        "frames": frames_payload,
    }


@app.get("/api/frame")
def get_frame(
    src: str = Query(..., description="Encoded IRSA access_url"),
    ra: float = Query(..., description="Right Ascension in degrees (0 to 360)"),
    dec: float = Query(..., description="Declination in degrees (-90 to 90)"),
    fov: float = Query(0.1, description="Field of view in degrees (0.02 to 0.5)"),
):
    if not src.startswith(IRSA_PREFIX):
        raise HTTPException(
            status_code=400,
            detail="Invalid 'src' URL. Only https://irsa.ipac.caltech.edu/ URLs are permitted.",
        )
    if not (0.0 <= ra <= 360.0):
        raise HTTPException(status_code=400, detail="Parameter 'ra' must be between 0 and 360.")
    if not (-90.0 <= dec <= 90.0):
        raise HTTPException(status_code=400, detail="Parameter 'dec' must be between -90 and 90.")
    if not (0.02 <= fov <= 0.5):
        raise HTTPException(status_code=400, detail="Parameter 'fov' must be between 0.02 and 0.5.")

    cache_key = cache.make_frame_key(src=src, ra=ra, dec=dec, fov=fov)
    cached_bytes = cache.get_cached_frame(cache_key)
    if cached_bytes is not None:
        return Response(
            content=cached_bytes,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    try:
        png_bytes = spherex.frame_png(access_url=src, ra=ra, dec=dec, fov=fov)
    except TimeoutError:
        raise HTTPException(status_code=504, detail="IRSA cutout download timed out.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to process cutout from IRSA: {exc}")

    cache.save_cached_frame(cache_key, png_bytes)

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )