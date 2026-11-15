import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="session")
def client():
    """HTTP test client for FastAPI."""
    return TestClient(app)


@pytest.fixture(scope="session")
def sample_fits_file() -> Path:
    """Returns the path of a locally cached real FITS file for testing."""
    fits_dir = Path("notebooks/data/spherex_cache/rw_aur")
    if not fits_dir.is_dir():
        pytest.skip("Test directory notebooks/data/spherex_cache/rw_aur not found")
    
    files = list(fits_dir.glob("*.fits"))
    if not files:
        pytest.skip("No FITS files available in test directory")
    
    return files[0]
