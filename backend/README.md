# SPHEREx Sky Viewer — Backend API

API FastAPI que busca observaciones de SPHEREx en IRSA y genera recortes,
animaciones, épocas y puntos de espectro bajo demanda. El backend no sirve
imágenes ni respuestas precalculadas como archivos estáticos: las vistas se
generan desde la API para cualquier coordenada.

## Datos y caché

- `GET /api/frames` consulta el catálogo SIA de IRSA. La respuesta de búsqueda
  se conserva 10 minutos y los metadatos de la secuencia también se reutilizan
  durante 10 minutos.
- `GET /api/frame` descarga con `fetch_cutout` el FITS del recorte solicitado.
  Los bytes se guardan en disco con una clave SHA-256 de
  `(access_url, ra, dec, fov)`. Una misma descarga concurrente comparte el
  resultado, y `/api/epochs` y `/api/spectrum` vuelven a usar esos mismos FITS.
- Los PNG procesados también se cachean. La caché conjunta de FITS, PNG y
  metadatos tiene un límite predeterminado de 2 GiB; al necesitar espacio,
  elimina primero las entradas más antiguas. Los recortes mayores que el límite
  no se guardan.
- Un semáforo limita a tres las descargas simultáneas a IRSA. El contenedor se
  ejecuta con un worker para que ese límite se aplique a todas sus peticiones.
- En Docker, monta un volumen persistente en `/app/data/cache` para conservar
  la caché entre reinicios. En otros entornos configura `SPHEREX_CACHE_DIR` a
  una ruta persistente.

No hay coordenadas con una caché o conjunto de imágenes especial: las claves
dependen de la URL y las coordenadas del recorte. El catálogo de
`GET /api/targets` solo proporciona sugerencias y metadatos de objetivos.

## Configuración

Todas las variables usan el prefijo `SPHEREX_`. Se pueden definir en el entorno
o en `backend/.env`; `backend/.env.example` contiene una plantilla.

| Variable | Predeterminado | Descripción |
| --- | --- | --- |
| `SPHEREX_HOST` | `0.0.0.0` | Dirección de escucha |
| `SPHEREX_PORT` | `8000` | Puerto HTTP |
| `SPHEREX_CORS_ORIGINS` | `["http://localhost:5173","http://127.0.0.1:5173"]` | Orígenes web permitidos, como una lista JSON |
| `SPHEREX_CACHE_DIR` | `backend/data/cache` | Caché persistente de FITS, PNG y metadatos |
| `SPHEREX_CACHE_MAX_BYTES` | `2147483648` | Tamaño máximo total de caché en bytes |
| `SPHEREX_METADATA_CACHE_TTL_SECONDS` | `600` | TTL de metadatos de secuencias |
| `SPHEREX_SEARCH_CACHE_TTL_SECONDS` | `600` | TTL de búsquedas SIA de IRSA |
| `SPHEREX_IRSA_TIMEOUT_SECONDS` | `60` | Timeout de acceso a IRSA |
| `SPHEREX_IRSA_MAX_RETRIES` | `4` | Reintentos de descargas |
| `SPHEREX_MAX_CONCURRENT_DOWNLOADS` | `3` | Descargas simultáneas permitidas |
| `SPHEREX_DEFAULT_DETECTOR` | `D2` | Detector por defecto (`D1`–`D6`) |
| `SPHEREX_DEFAULT_FOV` | `0.1` | Campo de visión por defecto, en grados |
| `SPHEREX_MAX_FRAMES` | `24` | Máximo de cuadros/puntos por petición |

Para producción, añade el **origen** del frontend desplegado a
`SPHEREX_CORS_ORIGINS`, conservando localhost para desarrollo. Por ejemplo:

```text
SPHEREX_CORS_ORIGINS=["https://mi-frontend.example.com","http://localhost:5173","http://127.0.0.1:5173"]
```

La API permite al navegador leer `X-Wavelength-Um` mediante
`Access-Control-Expose-Headers`.

## API

Las rutas de consulta aceptan coordenadas `ra` `[0, 360]`, `dec` `[-90, 90]`,
`fov` `[0.02, 0.5]`, detector `D1`–`D6` y `n` `[1, 24]`. También se puede usar
`target` en lugar de `ra` y `dec` para resolver un ID de `/api/targets`.
Parámetros inválidos o IDs desconocidos devuelven HTTP 400. Los errores se
devuelven como `{"error":"mensaje en inglés"}`; fallos de IRSA/procesamiento
usan 502 y timeouts usan 504.

### `GET /api/health`

Estado del servicio, permisos de escritura y conteos de las tres cachés.

### `GET /api/targets`

Catálogo de objetivos sugeridos. No proporciona imágenes ni secuencias
precalculadas.

### `GET /api/frames?ra=&dec=&fov=&detector=D2&n=16`

Busca observaciones y devuelve los cuadros ordenados temporalmente. Cada cuadro
incluye `url`, `mjd`, `date`, `detector` y `wavelength_um` (inicialmente
`null`). `url` apunta a `/api/frame`.

### `GET /api/frame?src=&ra=&dec=&fov=`

Descarga o reutiliza el FITS, lo alinea y devuelve `image/png`. `src` debe
empezar por `https://irsa.ipac.caltech.edu/`. La respuesta incluye
`Cache-Control` y, cuando se puede extraer del FITS, `X-Wavelength-Um`.

### `GET /api/epochs?ra=&dec=&fov=&detector=D2&n=16`

Usa la misma selección de observaciones que `/api/frames`, reutiliza los FITS
cacheados y devuelve `{target, detector, epochs, diffs}`. Las imágenes de
épocas y diferencias son URI `data:image/png;base64,...`; no requieren otra
ruta ni guardado de estado.

### `GET /api/spectrum?ra=&dec=&fov=&detector=D3&n=4`

Procesa un solo detector por llamada y devuelve `{target, detector, flux_unit,
aperture_arcsec, points}`. El valor predeterminado es `n=4`; la interfaz puede
hacer llamadas separadas para los detectores que quiera graficar.

Épocas y espectro están implementados en este backend. Si una futura
instalación no tiene disponible la implementación científica correspondiente,
la ruta debe responder HTTP 501 con `{"error":"Not available yet"}`.

## Desarrollo local

Requiere Python 3.11 o 3.12.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Swagger: `http://localhost:8000/docs` · Redoc: `http://localhost:8000/redoc`.
Desde la raíz del proyecto, también se puede arrancar con
`$env:PYTHONPATH="backend"; uvicorn app.main:app --reload --port 8000`.

## Pruebas

Desde `backend/`:

```powershell
pytest -v
```

Algunas pruebas de integración requieren FITS locales en
`notebooks/data/spherex_cache/rw_aur`; se omiten si no están disponibles.

## Docker y URL pública

Desde la raíz del proyecto:

```powershell
docker build -t spherex-backend .\backend
docker run --rm -p 8000:8000 -v spherex_cache:/app/data/cache spherex-backend
```

El backend no incluye una URL de producción ni una configuración de proveedor
de despliegue en este repositorio, así que todavía no hay una URL pública que
poner en `VITE_API_URL`. Después de desplegar el contenedor, usa la URL HTTPS
asignada por el proveedor (sin `/api` ni barra final), por ejemplo:

```text
VITE_API_URL=https://<dominio-publico-del-backend>
```

Configura ese dominio del frontend en `SPHEREX_CORS_ORIGINS` del backend y
mantén un volumen persistente para `/app/data/cache`.
