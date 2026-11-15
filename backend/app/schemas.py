from pydantic import BaseModel, Field


class TargetBase(BaseModel):
    name: str = Field(..., description="Identifier or display name of the astronomical target")
    ra: float = Field(..., ge=0.0, le=360.0, description="Right Ascension in degrees (0 to 360)")
    dec: float = Field(..., ge=-90.0, le=90.0, description="Declination in degrees (-90 to 90)")
    fov: float = Field(0.1, ge=0.02, le=0.5, description="Field of view in degrees (FOV)")


class TargetItem(TargetBase):
    id: str = Field(..., description="Canonical target ID (e.g., 'r_dra', 'barnard')")
    description: str | None = Field(None, description="Scientific description of the astronomical target")
    target_type: str = Field(
        ..., description="Simplified astronomical category: 'variable' or 'mover'"
    )
    pmra: float = Field(0.0, description="Proper motion in Right Ascension (mas/yr)")
    pmdec: float = Field(0.0, description="Proper motion in Declination (mas/yr)")
    epoch: float = Field(2000.0, description="Catalog reference epoch (e.g., J2000)")
    recommended_detector: str = Field("D2", description="Recommended SPHEREx detector for this target")


class TargetsListResponse(BaseModel):
    targets: list[TargetItem] = Field(..., description="List of available astronomical targets")
    total: int = Field(..., description="Total number of registered targets")


class FrameItem(BaseModel):
    url: str = Field(..., description="Absolute or relative URL to retrieve the processed PNG frame")
    mjd: float = Field(..., description="Modified Julian Date (MJD) of the observation")
    date: str = Field(..., description="Observation date in ISO format (YYYY-MM-DD)")
    detector: str = Field(..., description="SPHEREx detector identifier (D1 to D6)")
    wavelength_um: float | None = Field(
        None, description="Observed wavelength in micrometers at the target position"
    )
    obs_id: str | None = Field(None, description="SPHEREx observation identifier")


class FramesResponse(BaseModel):
    target: TargetBase = Field(..., description="Target metadata and observation field")
    frames: list[FrameItem] = Field(
        ..., description="Temporal sequence of frames available for animation"
    )
    total_frames: int = Field(..., description="Total number of frames in the sequence")
    source: str = Field("irsa", description="Data source origin ('irsa' or 'cache')")


class EpochItem(BaseModel):
    id: str = Field(..., description="Epoch identifier (e.g., 'e1')")
    url: str = Field(..., description="Stacked epoch image as a PNG data URI")
    date_start: str = Field(..., description="Date of the first frame in the epoch (YYYY-MM-DD)")
    date_end: str = Field(..., description="Date of the last frame in the epoch (YYYY-MM-DD)")
    mjd_mid: float = Field(..., description="Mean MJD of the frames in the epoch")
    n_frames: int = Field(..., description="Number of frames combined into the stack")


class DiffItem(BaseModel):
    url: str = Field(..., description="Difference image (b minus a) as a PNG data URI")
    a: str = Field(..., description="Earlier epoch id")
    b: str = Field(..., description="Later epoch id")


class EpochsResponse(BaseModel):
    target: TargetBase = Field(..., description="Queried target metadata")
    detector: str = Field(..., description="Analyzed detector")
    epochs: list[EpochItem] = Field(..., description="Stacked image per observing epoch, in time order")
    diffs: list[DiffItem] = Field(..., description="Differences between consecutive epochs")


class SpectrumPoint(BaseModel):
    wavelength_um: float = Field(..., description="Observed wavelength in micrometers")
    flux: float = Field(..., description="Background-subtracted flux in the target aperture")
    flux_err: float | None = Field(None, description="Estimated flux uncertainty")
    mjd: float = Field(..., description="Modified Julian Date (MJD)")
    date: str = Field(..., description="Observation date (YYYY-MM-DD)")
    detector: str = Field(..., description="Corresponding SPHEREx detector")
    obs_id: str | None = Field(None, description="Observation ID")
    saturated: bool = Field(
        False, description="Aperture contains saturated pixels; the flux is then a lower limit"
    )


class SpectrumResponse(BaseModel):
    target: TargetBase = Field(..., description="Queried target metadata")
    detector: str = Field(..., description="Analyzed detector")
    flux_unit: str = Field(..., description="Unit of flux and flux_err (e.g., 'mJy')")
    aperture_arcsec: float = Field(..., description="Side of the square photometry aperture in arcseconds")
    total_points: int = Field(..., description="Number of spectral points computed")
    points: list[SpectrumPoint] = Field(
        ..., description="Photometric and spectral points sorted by ascending wavelength"
    )


class HealthResponse(BaseModel):
    status: str = Field("ok", description="Operational status of the backend")
    version: str = Field(..., description="Backend software version")
    cache_dir: str = Field(..., description="Absolute path of the disk cache directory")
    cache_writable: bool = Field(
        ..., description="Indicates whether the process has write permissions to the cache"
    )
    cache_stats: dict[str, int] = Field(
        default_factory=dict, description="Statistics of stored elements in cache tiers"
    )


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Explanatory error message")
    detail: str | None = Field(None, description="Additional technical detail")