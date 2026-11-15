import os
from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base backend directory
BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    # API Metadata
    API_TITLE: str = "SPHEREx Sky Viewer API"
    API_VERSION: str = "0.1.0"
    API_DESCRIPTION: str = (
        "High-performance backend for exploration, time-series animation, and spectral analysis of NASA SPHEREx astronomical data."
    )
    DEBUG: bool = False

    # Server Network
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    ALLOWED_METHODS: list[str] = ["GET", "POST", "OPTIONS"]

    # Storage & Cache (Portable: defaults to backend/data/cache, configurable via SPHEREX_CACHE_DIR)
    CACHE_DIR: Path = Field(
        default_factory=lambda: Path(
            os.getenv("SPHEREX_CACHE_DIR", str(BACKEND_DIR / "data" / "cache"))
        )
    )
    # Optional local FITS store used to seed the shared cutout cache
    RAW_FITS_DIR: Path = Field(
        default_factory=lambda: Path(
            os.getenv(
                "SPHEREX_RAW_FITS_DIR",
                str(PROJECT_ROOT / "notebooks" / "data" / "spherex_cache"),
            )
        )
    )

    # Cache TTL & Limits
    METADATA_CACHE_TTL_SECONDS: int = 600  # 10 minutes
    SEARCH_CACHE_TTL_SECONDS: int = 600  # 10 minutes
    CACHE_MAX_BYTES: int = 2 * 1024**3
    FRAME_CACHE_MAX_AGE_SECONDS: int = 86400  # HTTP Cache-Control header

    # External Services (NASA / IPAC / IRSA)
    IRSA_PREFIX: str = "https://irsa.ipac.caltech.edu/"
    IRSA_TIMEOUT_SECONDS: float = 60.0
    IRSA_MAX_RETRIES: int = 4
    MAX_CONCURRENT_DOWNLOADS: int = 3  # Protect IRSA from connection flooding

    # Astronomical Defaults
    ALLOWED_DETECTORS: list[str] = ["D1", "D2", "D3", "D4", "D5", "D6"]
    DEFAULT_DETECTOR: str = "D2"
    DEFAULT_FOV: float = 0.1
    MAX_FRAMES: int = 24
    REFERENCE_EPOCH: str = "2026-01-01"

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        env_prefix="SPHEREX_",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Returns a cached instance of application settings."""
    settings = Settings()
    # Ensure cache directory exists
    settings.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return settings
