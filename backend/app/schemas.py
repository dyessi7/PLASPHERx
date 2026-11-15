from pydantic import BaseModel, Field


class TargetBase(BaseModel):
    name: str = Field(..., description="Identificador o nombre del objetivo astronómico")
    ra: float = Field(..., ge=0.0, le=360.0, description="Ascensión Recta en grados (0 a 360)")
    dec: float = Field(..., ge=-90.0, le=90.0, description="Declinación en grados (-90 a 90)")
    fov: float = Field(0.1, ge=0.02, le=0.5, description="Campo de visión en grados (FOV)")


class TargetItem(TargetBase):
    id: str = Field(..., description="ID canónico del objetivo (ej: 'r_dra', 'barnard')")
    description: str | None = Field(None, description="Descripción científica del objetivo")
    target_type: str = Field(
        ..., description="Tipo astronómico simplificado: 'variable' o 'mover'"
    )
    pmra: float = Field(0.0, description="Movimiento propio en RA (mas/año)")
    pmdec: float = Field(0.0, description="Movimiento propio en Dec (mas/año)")
    epoch: float = Field(2000.0, description="Época del catálogo astronómico (ej: J2000)")
    recommended_detector: str = Field("D2", description="Detector recomendado para este objetivo")


class TargetsListResponse(BaseModel):
    targets: list[TargetItem] = Field(..., description="Lista de objetivos astronómicos disponibles")
    total: int = Field(..., description="Número total de objetivos registrados")


class FrameItem(BaseModel):
    url: str = Field(..., description="URL absoluta o relativa para obtener la imagen PNG del cuadro")
    mjd: float = Field(..., description="Fecha Juliana Modificada (MJD) de la observación")
    date: str = Field(..., description="Fecha en formato ISO (YYYY-MM-DD)")
    detector: str = Field(..., description="Detector SPHEREx utilizado (D1 a D6)")
    wavelength_um: float | None = Field(
        None, description="Longitud de onda en micrómetros en la posición del objetivo"
    )
    obs_id: str | None = Field(None, description="Identificador de la observación SPHEREx")


class FramesResponse(BaseModel):
    target: TargetBase = Field(..., description="Metadatos de la posición y campo observado")
    frames: list[FrameItem] = Field(
        ..., description="Secuencia temporal de cuadros disponibles para animación"
    )
    total_frames: int = Field(..., description="Cantidad total de cuadros en la secuencia")
    source: str = Field("irsa", description="Origen de los datos ('irsa' o 'cache')")


class EpochItem(BaseModel):
    epoch_index: int = Field(..., description="Número ordinal de la época de observación")
    label: str = Field(..., description="Etiqueta legible de la época (ej: 'Época 1 (Jun 2025)')")
    mjd_start: float = Field(..., description="MJD inicial de la época")
    mjd_end: float = Field(..., description="MJD final de la época")
    mjd_mean: float = Field(..., description="MJD medio de la época")
    start_date: str = Field(..., description="Fecha inicial en formato ISO (YYYY-MM-DD)")
    end_date: str = Field(..., description="Fecha final en formato ISO (YYYY-MM-DD)")
    frame_count: int = Field(..., description="Número de cuadros contenidos en esta época")
    detector: str = Field(..., description="Detector utilizado")
    frames: list[FrameItem] = Field(..., description="Lista de cuadros de esta época")


class EpochsResponse(BaseModel):
    target: TargetBase = Field(..., description="Metadatos del objetivo consultado")
    detector: str = Field(..., description="Detector analizado")
    total_epochs: int = Field(..., description="Cantidad total de épocas detectadas")
    epochs: list[EpochItem] = Field(..., description="Lista de agrupaciones temporales por época")


class SpectrumPoint(BaseModel):
    wavelength_um: float = Field(..., description="Longitud de onda observada en micrómetros")
    flux: float = Field(..., description="Flujo integrado en la apertura del objetivo (cuentas netas)")
    flux_err: float | None = Field(None, description="Incertidumbre estimada del flujo")
    mjd: float = Field(..., description="Fecha Juliana Modificada (MJD)")
    date: str = Field(..., description="Fecha de observación (YYYY-MM-DD)")
    detector: str = Field(..., description="Detector SPHEREx correspondiente")
    obs_id: str | None = Field(None, description="ID de observación")


class SpectrumResponse(BaseModel):
    target: TargetBase = Field(..., description="Metadatos del objetivo consultado")
    detector: str = Field(..., description="Detector analizado")
    total_points: int = Field(..., description="Cantidad de puntos espectrales calculados")
    points: list[SpectrumPoint] = Field(
        ..., description="Puntos de fotometría/espectro ordenados por longitud de onda ascendente"
    )


class HealthResponse(BaseModel):
    status: str = Field("ok", description="Estado operativo del backend")
    version: str = Field(..., description="Versión del backend")
    cache_dir: str = Field(..., description="Ruta absoluta del directorio de caché")
    cache_writable: bool = Field(
        ..., description="Indica si el sistema tiene permisos de escritura en la caché"
    )
    cache_stats: dict[str, int] = Field(
        default_factory=dict, description="Estadísticas de elementos almacenados en caché"
    )


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Mensaje explicativo del error")
    detail: str | None = Field(None, description="Detalle técnico adicional")
