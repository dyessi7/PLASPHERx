# 🔭 SPHEREx Sky Viewer - Backend API

Backend de alto rendimiento construido con **FastAPI**, **Pydantic** y el stack astronómico de Python (**Astropy**, **Reproject**, **Astroquery**) para la ingesta, alineación, animación temporal y visualización de datos espectroscópicos de la misión **NASA SPHEREx**.

---

## 🚀 Características Principales

* **Pipeline Científico Preciso:** Reproyección WCS (`reproject_interp`), sustracción de fondo astronómico, contraste por percentiles (Z-Scale) y extracción de longitudes de onda en micrómetros.
* **Modo Híbrido de Alto Rendimiento:**
  * **Instantáneo:** Entrega inmediata de secuencias precalculadas para los objetivos principales del catálogo (*R Draconis, Barnard's Star, WISE 0855, RW Aurigae, Epsilon Indi*).
  * **On-Demand:** Búsqueda y recorte dinámico sobre los archivos FITS de IRSA/IPAC para cualquier coordenada del cielo.
* **Caché Inteligente de Doble Nivel:** Almacena tanto los metadatos SIA como las imágenes PNG procesadas, evitando saturar los servidores de la NASA con consultas redundantes.
* **Control de Concurrencia y Resiliencia:** Semáforo de descargas y políticas de reintento (*exponential backoff*) para evitar bloqueos por *rate-limiting* (`429 / ConnectionReset`).
* **Soporte de Movimiento Propio (*Proper Motion*):** Corrección cinemática automática de coordenadas J2000 hacia la época de observación (2025–2026).
* **Documentación Interactiva Automática:** Esquemas OpenAPI 3.1 disponibles en `/docs` (Swagger UI) y `/redoc`.

---

## 📂 Estructura del Backend

```text
backend/
├── app/
│   ├── __init__.py
│   ├── config.py         # Configuración centralizada y lectura de variables de entorno (BaseSettings)
│   ├── schemas.py        # Modelos Pydantic para tipado estricto de Request y Response
│   ├── cache.py          # Manejo de caché en disco (frames PNG y metadatos JSON)
│   ├── spherex.py        # Pipeline astronómico (IRSA SIA, WCS, reproyección y contrastes)
│   └── main.py           # Instancia principal de FastAPI, middlewares y rutas de la API
├── data/
│   └── cache/            # Directorio local persistente para recortes e índices
│       ├── frames/       # Imágenes procesadas en formato PNG
│       └── metadata/     # Metadatos cacheados de consultas SIA
├── Dockerfile            # Configuración para despliegue en contenedores Docker
├── requirements.txt      # Dependencias fijadas del proyecto
├── .env.example          # Plantilla de variables de entorno
└── README.md             # Esta documentación
```

---

## ⚙️ Configuración y Variables de Entorno

El backend utiliza `pydantic-settings` para cargar configuraciones desde variables de entorno o un archivo `.env` en la raíz de `backend/`. Todas las variables cuentan con el prefijo `SPHEREX_`:

| Variable | Tipo | Valor por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `SPHEREX_DEBUG` | `bool` | `False` | Habilita logs detallados de desarrollo |
| `SPHEREX_PORT` | `int` | `8000` | Puerto HTTP del servidor |
| `SPHEREX_HOST` | `str` | `"0.0.0.0"` | Interfaz de red de enlace |
| `SPHEREX_CORS_ORIGINS` | `list` | `["*"]` | Lista de dominios autorizados para CORS |
| `SPHEREX_CACHE_DIR` | `Path` | `./data/cache` | Ruta del directorio persistente de caché |
| `SPHEREX_PRECOMPUTED_DIR` | `Path` | `../frontend/public/data` | Ruta de datasets precalculados |
| `SPHEREX_IRSA_TIMEOUT_SECONDS` | `float` | `60.0` | Timeout máximo para peticiones a IRSA |
| `SPHEREX_MAX_CONCURRENT_DOWNLOADS` | `int` | `3` | Límite de descargas simultáneas a IRSA |
| `SPHEREX_DEFAULT_DETECTOR` | `str` | `"D2"` | Detector por defecto (D1 a D6) |
| `SPHEREX_DEFAULT_FOV` | `float` | `0.1` | Campo de visión por defecto en grados |
| `SPHEREX_MAX_FRAMES` | `int` | `24` | Límite máximo de cuadros por secuencia |

---

## 📡 Especificación de la API

### 1. `GET /api/health`
Verifica el estado del servicio, detecta permisos de escritura en la caché y reporta qué objetivos precalculados están listos para servirse.
* **Respuesta 200:**
  ```json
  {
    "status": "ok",
    "version": "0.1.0",
    "cache_dir": "/app/data/cache",
    "cache_writable": true,
    "precomputed_targets": ["r_dra", "barnard"]
  }
  ```

### 2. `GET /api/targets`
Devuelve el catálogo de objetivos destacados del reto con sus datos cinemáticos corregidos por movimiento propio a 2026 y el indicador `is_precomputed`.
* **Respuesta 200:**
  ```json
  {
    "targets": [
      {
        "id": "r_dra",
        "name": "R Draconis",
        "description": "Estrella variable gigante roja tipo Mira con variación periódica de brillo.",
        "target_type": "variable_star",
        "ra": 248.1675,
        "dec": 66.7550,
        "fov": 0.1,
        "pmra": 0.0,
        "pmdec": 0.0,
        "epoch": 2000.0,
        "is_precomputed": true
      },
      {
        "id": "barnard",
        "name": "Barnard's Star",
        "description": "Enana roja cercana con el mayor movimiento propio conocido (10.3 arcsec/año).",
        "target_type": "high_proper_motion",
        "ra": 269.446268,
        "dec": 4.768227,
        "fov": 0.1,
        "pmra": -802.0,
        "pmdec": 10362.0,
        "epoch": 2000.0,
        "is_precomputed": false
      }
    ],
    "total": 5
  }
  ```

### 3. `GET /api/frames`
Obtiene la secuencia temporal de observaciones para una posición dada.
* **Parámetros de consulta (Query Params):**
  * `ra` *(float, obligatorio)*: Ascensión Recta en grados `[0.0, 360.0]`.
  * `dec` *(float, obligatorio)*: Declinación en grados `[-90.0, 90.0]`.
  * `fov` *(float, opcional, default: `0.1`)*: Campo de visión en grados `[0.02, 0.5]`.
  * `detector` *(string, opcional, default: `"D2"`)*: Detector SPHEREx (`D1` a `D6`).
  * `n` *(int, opcional, default: `16`)*: Número de cuadros temporales `[1, 24]`.
* **Respuesta 200:**
  ```json
  {
    "target": {
      "name": "custom_248.1675_66.7550",
      "ra": 248.1675,
      "dec": 66.7550,
      "fov": 0.1
    },
    "frames": [
      {
        "url": "http://localhost:8000/api/frame?src=...&ra=248.1675&dec=66.7550&fov=0.1",
        "mjd": 60814.46,
        "date": "2025-05-19",
        "detector": "D2",
        "wavelength_um": 2.415,
        "obs_id": "spherex_obs_01"
      }
    ],
    "total_frames": 16,
    "source": "irsa"
  }
  ```

### 4. `GET /api/frame`
Descarga, alinea y genera la imagen PNG individual para un cuadro dado.
* **Parámetros:** `src` (URL oficial de IRSA codificada), `ra`, `dec`, `fov`.
* **Respuesta:** Imagen binaria con cabeceras HTTP de caché (`image/png`, `Cache-Control: public, max-age=86400`).

### 5. `GET /api/epochs`
Agrupa las observaciones temporales en épocas astronómicas (*surveys* o pasadas semestrales de SPHEREx) utilizando `build_epochs`.
* **Parámetros:** `target` (o `ra` y `dec`), `detector` (default `"D2"`), `threshold_days` (default `45.0`).
* **Respuesta 200:**
  ```json
  {
    "target": {
      "name": "RW Aurigae",
      "ra": 76.95642,
      "dec": 30.40142,
      "fov": 0.1
    },
    "detector": "D2",
    "total_epochs": 2,
    "epochs": [
      {
        "epoch_index": 1,
        "label": "Época 1 (Jun 2025)",
        "mjd_start": 60834.788,
        "mjd_end": 60858.909,
        "mjd_mean": 60846.85,
        "start_date": "2025-06-08",
        "end_date": "2025-07-02",
        "frame_count": 6,
        "detector": "D2",
        "frames": [ ... ]
      }
    ]
  }
  ```

### 6. `GET /api/spectrum`
Calcula puntos de fotometría de apertura y espectro astronómico ($F(\lambda)$ vs longitud de onda) utilizando `spectrum_points`.
* **Parámetros:** `target` (o `ra` y `dec`), `detector` (default `"D2"`), `n` (máx cuadros a procesar).
* **Respuesta 200:**
  ```json
  {
    "target": {
      "name": "RW Aurigae",
      "ra": 76.95642,
      "dec": 30.40142,
      "fov": 0.1
    },
    "detector": "D2",
    "total_points": 6,
    "points": [
      {
        "wavelength_um": 1.0941,
        "flux": 266.2257,
        "flux_err": 12.4312,
        "mjd": 60834.788,
        "date": "2025-06-08",
        "detector": "D2",
        "obs_id": "spherex_obs_01"
      }
    ]
  }
  ```

---

## 🛠️ Puesta en Marcha Local

### Prerrequisitos
* Python 3.11 o 3.12 instalado.
* Entorno virtual activo.

### 1. Instalación de dependencias
```bash
cd backend
pip install -r requirements.txt
```

### 2. Ejecución del servidor
Desde la carpeta raíz del proyecto:
```bash
# Windows PowerShell
$env:PYTHONPATH="backend"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
O directamente desde la carpeta `backend`:
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Explorar la documentación interactiva
* Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
* Redoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🧪 Pruebas Automatizadas (Pytest)

El backend cuenta con una suite completa de pruebas unitarias y de integración que validan el catálogo, la cinemática astronómica, el pipeline de reproyección FITS/PNG, los endpoints de épocas y espectro, y la protección contra ataques SSRF.

Para ejecutar todas las pruebas:
```bash
# Desde la raíz del repositorio
pytest backend/tests -v

# O desde la carpeta backend/
cd backend
pytest -v
```

---

## 🐳 Ejecución con Docker

El `Dockerfile` está optimizado para entornos de producción con usuario sin privilegios (`appuser`), verificación periódica de salud (`HEALTHCHECK`) y volumen persistente de caché.

Para construir y desplegar el contenedor:
```bash
# Construir la imagen
docker build -t spherex-backend ./backend

# Ejecutar el contenedor mapeando el puerto y persistiendo la caché
docker run -d -p 8000:8000 -v spherex_cache:/app/data/cache --name spherex-api spherex-backend
```

---

## 🧪 Calidad de Código y Arquitectura

* **Separación de Responsabilidades:** El controlador web (`main.py`) no conoce los detalles de astrometría; delega la ciencia en `spherex.py` y el almacenamiento en `cache.py`.
* **Zero Trust en Entradas Externas:** Toda coordenada, FOV y URL externa pasa por validación estricta de rangos para evitar ataques de inyección o SSRF.
* **Persistencia Portátil:** Rutas dinámicas mediante `pathlib.Path` que funcionan sin cambios en Windows, macOS y entornos Linux de producción.
