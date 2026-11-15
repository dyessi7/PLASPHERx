import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="session")
def client():
    """Cliente de pruebas HTTP para FastAPI."""
    return TestClient(app)


@pytest.fixture(scope="session")
def sample_fits_file() -> Path:
    """Retorna la ruta de un archivo FITS real descargado localmente para pruebas."""
    fits_dir = Path("notebooks/data/spherex_cache/rw_aur")
    if not fits_dir.is_dir():
        pytest.skip("No se encontró el directorio notebooks/data/spherex_cache/rw_aur")
    
    files = list(fits_dir.glob("*.fits"))
    if not files:
        pytest.skip("No hay archivos FITS disponibles en el directorio de pruebas")
    
    return files[0]
