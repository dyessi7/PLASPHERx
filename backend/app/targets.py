import warnings
from typing import Any
from app.config import get_settings
from app.schemas import TargetItem

settings = get_settings()

# Official dictionary of the 5 predefined targets for SPHEREx / Planet X
TARGETS_CATALOG: dict[str, dict[str, Any]] = {
    "r_dra": {
        "id": "r_dra",
        "name": "R Draconis",
        "description": "Mira-type red giant variable star with periodic brightness pulsations and mass loss.",
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
        "description": "Young T Tauri binary star system exhibiting deep optical dimming events from circumstellar dust.",
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
        "description": "Nearby red dwarf star with the largest known proper motion in the sky (10.3 arcsec/yr).",
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
        "description": "Ultra-cool sub-brown dwarf (spectral class Y), the coldest known sub-stellar object outside the Solar System.",
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
        "description": "Nearby stellar system hosting a brown dwarf binary pair and a confirmed Jovian exoplanet.",
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
    """Calculates the target's position (RA, Dec) in degrees corrected for proper motion at a given date."""
    if target_id not in TARGETS_CATALOG:
        raise ValueError(f"Target '{target_id}' not found in catalog.")

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
    """Retrieves target metadata. If apply_pm=True, returns coordinates propagated to the reference epoch."""
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
    """Returns the 5 predefined targets with their base coordinates and category ('variable' or 'mover')."""
    result: list[TargetItem] = []
    for tid in TARGETS_CATALOG:
        item = get_target_by_id(tid, apply_pm=apply_pm)
        if item:
            result.append(item)
    return result


def find_target_by_coords(ra: float, dec: float, tolerance_deg: float = 0.05) -> TargetItem | None:
    """Identifies whether given (RA, Dec) coordinates match a known catalog target within tolerance."""
    import math

    for tid, _ in TARGETS_CATALOG.items():
        tra, tdec = calculate_target_position(tid, settings.REFERENCE_EPOCH)
        dra = (ra - tra) * math.cos(math.radians((dec + tdec) / 2.0))
        ddec = dec - tdec
        dist = math.sqrt(dra * dra + ddec * ddec)
        if dist <= tolerance_deg:
            return get_target_by_id(tid, apply_pm=True)
    return None
