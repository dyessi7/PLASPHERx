import warnings
from typing import Any
from app.config import get_settings
from app.schemas import TargetItem

settings = get_settings()

# Diccionario oficial de los 5 objetivos predefinidos para SPHEREx / Planet X
TARGETS_CATALOG: dict[str, dict[str, Any]] = {
    "r_dra": {
        "id": "r_dra",
        "name": "R Draconis",
        "description": "Estrella variable gigante roja tipo Mira con variación periódica de brillo.",
        "target_type": "variable",
        "ra": 248.1675,
        "dec": 66.7550,
        "pmra": 0.0,
        "pmdec": 0.0,
        "epoch": 2000.0,
        "fov": 0.1,
        "recommended_detector": "D2",
    },
    "rw_aur": {
        "id": "rw_aur",
        "name": "RW Aurigae",
        "description": "Sistema estelar binario joven tipo T Tauri con atenuaciones ópticas profundas.",
        "target_type": "variable",
        "ra": 76.95642,
        "dec": 30.40142,
        "pmra": 0.0,
        "pmdec": 0.0,
        "epoch": 2000.0,
        "fov": 0.1,
        "recommended_detector": "D2",
    },
    "barnard": {
        "id": "barnard",
        "name": "Barnard's Star",
        "description": "Enana roja cercana con el mayor movimiento propio conocido en el cielo (10.3 arcsec/año).",
        "target_type": "mover",
        "ra": 269.45208,
        "dec": 4.69339,
        "pmra": -802.0,
        "pmdec": 10362.0,
        "epoch": 2000.0,
        "fov": 0.1,
        "recommended_detector": "D2",
    },
    "wise0855": {
        "id": "wise0855",
        "name": "WISE J0855-0714",
        "description": "Enana sub-marrón ultrafía (tipo Y), el objeto subestelar más frío fuera del Sistema Solar.",
        "target_type": "mover",
        "ra": 133.79513,
        "dec": -7.24515,
        "pmra": -8120.0,
        "pmdec": 680.0,
        "epoch": 2010.5,
        "fov": 0.1,
        "recommended_detector": "D2",
    },
    "eps_ind": {
        "id": "eps_ind",
        "name": "Epsilon Indi",
        "description": "Sistema estelar cercano que alberga un par de enanas marrones y un exoplaneta gigante.",
        "target_type": "mover",
        "ra": 331.0438,
        "dec": -56.7827,
        "pmra": 3960.0,
        "pmdec": -2540.0,
        "epoch": 2000.0,
        "fov": 0.2,
        "recommended_detector": "D2",
    },
}


def calculate_target_position(target_id: str, date_str: str = "2026-01-01") -> tuple[float, float]:
    """Calcula la posición (RA, Dec) en grados corregida por movimiento propio para una fecha dada."""
    if target_id not in TARGETS_CATALOG:
        raise ValueError(f"Objetivo '{target_id}' no encontrado en el catálogo.")

    o = TARGETS_CATALOG[target_id]
    pmra = o.get("pmra", 0.0)
    pmdec = o.get("pmdec", 0.0)

    if pmra == 0.0 and pmdec == 0.0:
        return float(o["ra"]), float(o["dec"])

    try:
        import astropy.units as u
        from astropy.coordinates import SkyCoord
        from astropy.time import Time

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            coord = SkyCoord(
                ra=o["ra"] * u.deg,
                dec=o["dec"] * u.deg,
                pm_ra_cosdec=pmra * u.mas / u.yr,
                pm_dec=pmdec * u.mas / u.yr,
                obstime=Time(o["epoch"], format="jyear"),
                frame="icrs",
            )
            hoy = coord.apply_space_motion(new_obstime=Time(date_str))
            return float(round(hoy.ra.deg, 6)), float(round(hoy.dec.deg, 6))
    except Exception:
        import math
        from datetime import datetime

        dt = datetime.fromisoformat(date_str).year - o["epoch"]
        ra_deg = o["ra"] + (pmra / (1000.0 * 3600.0 * math.cos(math.radians(o["dec"])))) * dt
        dec_deg = o["dec"] + (pmdec / (1000.0 * 3600.0)) * dt
        return float(round(ra_deg, 6)), float(round(dec_deg, 6))


def get_target_by_id(target_id: str, apply_pm: bool = True) -> TargetItem | None:
    """Retorna los metadatos de un objetivo. Si apply_pm=True, entrega las coordenadas actualizadas a 2026."""
    target_id_clean = target_id.lower().strip()
    if target_id_clean not in TARGETS_CATALOG:
        return None

    data = TARGETS_CATALOG[target_id_clean]
    if apply_pm:
        ra_val, dec_val = calculate_target_position(target_id_clean, settings.REFERENCE_EPOCH)
    else:
        ra_val, dec_val = float(data["ra"]), float(data["dec"])

    return TargetItem(
        id=data["id"],
        name=data["name"],
        description=data.get("description"),
        target_type=data.get("target_type", "variable"),
        ra=ra_val,
        dec=dec_val,
        fov=data.get("fov", settings.DEFAULT_FOV),
        pmra=data.get("pmra", 0.0),
        pmdec=data.get("pmdec", 0.0),
        epoch=data.get("epoch", 2000.0),
        recommended_detector=data.get("recommended_detector", "D2"),
    )


def list_targets(apply_pm: bool = False) -> list[TargetItem]:
    """Retorna los 5 objetivos predefinidos con sus coordenadas base y tipo (variable o mover)."""
    result: list[TargetItem] = []
    for tid in TARGETS_CATALOG:
        item = get_target_by_id(tid, apply_pm=apply_pm)
        if item:
            result.append(item)
    return result


def find_target_by_coords(ra: float, dec: float, tolerance_deg: float = 0.05) -> TargetItem | None:
    """Identifica si unas coordenadas (ra, dec) dadas corresponden a un objetivo conocido dentro de la tolerancia."""
    import math

    for tid, _ in TARGETS_CATALOG.items():
        tra, tdec = calculate_target_position(tid, settings.REFERENCE_EPOCH)
        dra = (ra - tra) * math.cos(math.radians((dec + tdec) / 2.0))
        ddec = dec - tdec
        dist = math.sqrt(dra * dra + ddec * ddec)
        if dist <= tolerance_deg:
            return get_target_by_id(tid, apply_pm=True)
    return None
