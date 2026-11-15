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
    epoch_index: int = Field(..., description="Ordinal number of the observation epoch")
    label: str = Field(..., description="Human-readable epoch label (e.g., 'Epoch 1 (Jun 2025)')")
    mjd_start: float = Field(..., description="Starting MJD of the epoch")
    mjd_end: float = Field(..., description="Ending MJD of the epoch")
    mjd_mean: float = Field(..., description="Mean MJD of the epoch")
    start_date: str = Field(..., description="Starting date in ISO format (YYYY-MM-DD)")
    end_date: str = Field(..., description="Ending date in ISO format (YYYY-MM-DD)")
    frame_count: int = Field(..., description="Number of frames contained in this epoch")
    detector: str = Field(..., description="SPHEREx detector identifier")
    frames: list[FrameItem] = Field(..., description="List of frames within this epoch")


class EpochsResponse(BaseModel):
    target: TargetBase = Field(..., description="Queried target metadata")
    detector: str = Field(..., description="Analyzed detector")
    total_epochs: int = Field(..., description="Total number of detected survey epochs")
    epochs: list[EpochItem] = Field(..., description="List of temporal clusters grouped by epoch")


class SpectrumPoint(BaseModel):
    wavelength_um: float = Field(..., description="Observed wavelength in micrometers")
    flux: float = Field(..., description="Integrated flux in the target aperture (net counts)")
    flux_err: float | None = Field(None, description="Estimated flux uncertainty")
    mjd: float = Field(..., description="Modified Julian Date (MJD)")
    date: str = Field(..., description="Observation date (YYYY-MM-DD)")
    detector: str = Field(..., description="Corresponding SPHEREx detector")
    obs_id: str | None = Field(None, description="Observation ID")


class SpectrumResponse(BaseModel):
    target: TargetBase = Field(..., description="Queried target metadata")
    detector: str = Field(..., description="Analyzed detector")
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
