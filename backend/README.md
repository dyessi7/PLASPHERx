# SPHEREx Sky Viewer — Backend API

FastAPI backend that queries SPHEREx observations from IRSA and generates cutouts, animations, epochs, and spectrum data points on demand. The backend does not serve precomputed static images or responses: views are generated on-the-fly from the API for any celestial coordinates.

## Data and Caching

- `GET /api/frames` queries the IRSA SIA catalog. Search results are cached for 10 minutes, and frame sequence metadata is likewise reused for 10 minutes.
- `GET /api/frame` downloads the requested cutout FITS via `fetch_cutout`. Raw bytes are stored on disk using a SHA-256 hash of `(access_url, ra, dec, fov)`. Concurrent requests for the same cutout share a single in-flight download, and both `/api/epochs` and `/api/spectrum` reuse these cached FITS files.
- Processed PNGs are also cached. The combined disk cache for FITS, PNG, and metadata has a default size limit of 2 GiB (`SPHEREX_CACHE_MAX_BYTES`); when additional space is required, it evicts the least recently modified entries (LRU). Cutouts larger than the total limit are not persisted.
- A concurrency semaphore limits simultaneous download connections to IRSA to 3. The Docker container runs with a single worker process so this limit applies globally across all incoming requests.
- In Docker, mount a persistent volume at `/app/data/cache` to preserve the cache across container restarts. In other deployment environments, configure `SPHEREX_CACHE_DIR` to a persistent path.

No coordinates or targets use hardcoded or special caches: cache keys depend strictly on the observation access URL and cutout sky parameters. The `GET /api/targets` catalog provides only suggested targets and reference metadata.

## Configuration

All environment variables use the `SPHEREX_` prefix. They can be set in the system environment or in `backend/.env` (a template is available in `backend/.env.example`).

| Variable | Default | Description |
| --- | --- | --- |
| `SPHEREX_HOST` | `0.0.0.0` | Listen network interface |
| `SPHEREX_PORT` | `8000` | HTTP listen port |
| `SPHEREX_CORS_ORIGINS` | `["http://localhost:5173","http://127.0.0.1:5173"]` | Allowed CORS origins, formatted as a JSON list |
| `SPHEREX_CACHE_DIR` | `backend/data/cache` | Persistent disk cache directory for FITS, PNG, and metadata |
| `SPHEREX_CACHE_MAX_BYTES` | `2147483648` | Maximum cache size in bytes (default: 2 GiB) |
| `SPHEREX_METADATA_CACHE_TTL_SECONDS` | `600` | Sequence metadata cache TTL in seconds |
| `SPHEREX_SEARCH_CACHE_TTL_SECONDS` | `600` | IRSA SIA search queries TTL in seconds |
| `SPHEREX_IRSA_TIMEOUT_SECONDS` | `60` | Network timeout for IRSA requests in seconds |
| `SPHEREX_IRSA_MAX_RETRIES` | `4` | Retry attempts for network cutouts |
| `SPHEREX_MAX_CONCURRENT_DOWNLOADS` | `3` | Maximum concurrent downloads to IRSA |
| `SPHEREX_DEFAULT_DETECTOR` | `D2` | Default detector band (`D1`–`D6`) |
| `SPHEREX_DEFAULT_FOV` | `0.1` | Default field of view in degrees |
| `SPHEREX_MAX_FRAMES` | `24` | Maximum frames or spectrum points per request |

For production, add the deployed frontend **origin** to `SPHEREX_CORS_ORIGINS`, retaining localhost origins for local development. For example:

```text
SPHEREX_CORS_ORIGINS=["https://my-frontend.example.com","http://localhost:5173","http://127.0.0.1:5173"]
```

The API exposes `X-Wavelength-Um` via `Access-Control-Expose-Headers` so browser clients can read the extracted wavelength from frame responses.

## API Endpoints

Query routes accept coordinates `ra` in `[0, 360]`, `dec` in `[-90, 90]`, `fov` in `[0.02, 0.5]`, detector `D1`–`D6`, and `n` in `[1, 24]`. You can also provide `target` instead of `ra` and `dec` to resolve a known target identifier from `/api/targets`. Invalid query parameters or unrecognized target IDs return HTTP 400. Errors follow the format `{"error": "description"}`; IRSA/processing failures return 502 and timeouts return 504.

### `GET /api/health`

Returns service health status, cache directory write permissions, and object counts across the three cache tiers (PNG frames, metadata queries, and raw FITS).

### `GET /api/targets`

Returns the catalog of 5 predefined astronomical targets (`r_dra`, `rw_aur`, `barnard`, `wise0855`, `eps_ind`) with their types (`variable` or `mover`) and base coordinates. Does not provide precomputed images or static sequences.

### `GET /api/frames?ra=&dec=&fov=&detector=D2&n=16`

Searches IRSA observations and returns temporally ordered frame metadata. Each frame object includes `url`, `mjd`, `date`, `detector`, and `wavelength_um` (initially `null`). `url` points to the on-the-fly `/api/frame` endpoint.

### `GET /api/frame?src=&ra=&dec=&fov=`

Fetches or reuses the FITS cutout, aligns the celestial image (WCS re-projection), and streams `image/png`. `src` must start with `https://irsa.ipac.caltech.edu/`. Responses include HTTP `Cache-Control` headers and, when available from the FITS WCS, the `X-Wavelength-Um` header.

### `GET /api/epochs?ra=&dec=&fov=&detector=D2&n=16&threshold_days=45`

Shares the same observation selection as `/api/frames`, reuses cached FITS files, clusters frames into survey epochs by timeline gap (`threshold_days`), stacks aligned arrays per epoch, and computes consecutive difference images (`stacks[i] - stacks[i - 1]`). Returns `{target, detector, epochs, diffs}` where all images are base64 `data:image/png;base64,...` data URIs for immediate UI rendering without secondary requests.

### `GET /api/spectrum?ra=&dec=&fov=&detector=D3&n=4`

Performs aperture photometry at the target coordinate across observations for a specific detector, converting surface brightness (MJy/sr) to integrated flux (mJy). Returns `{target, detector, flux_unit, aperture_arcsec, total_points, points}` sorted in ascending order of wavelength.

## Local Development

Requires Python 3.11 or 3.12.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Interactive OpenAPI Swagger docs: `http://localhost:8000/docs`
- Interactive ReDoc docs: `http://localhost:8000/redoc`

You can also run directly from the repository root:
```powershell
$env:PYTHONPATH="backend"; uvicorn app.main:app --reload --port 8000
```

## Running Tests

From the repository root or `backend/`:

```powershell
$env:PYTHONPATH="backend"; pytest backend/tests -v
```

Tests include full pipeline unit tests, cache LRU eviction tests, proper motion kinematic tests, and mock/integration API tests. Integration tests requiring real sample FITS use files in `notebooks/data/spherex_cache/rw_aur` and gracefully skip if not present.

## Docker Deployment

Build and run the container image:

```powershell
docker build -t spherex-backend .\backend
docker run --rm -p 8000:8000 -v spherex_cache:/app/data/cache spherex-backend
```

Configure the frontend environment variable `VITE_API_URL` to point to the deployed backend URL (without `/api` or a trailing slash):

```text
VITE_API_URL=https://<your-backend-domain>
```

Ensure that this frontend URL is included in the backend's `SPHEREX_CORS_ORIGINS` environment variable and that a persistent storage volume is mounted at `/app/data/cache`.
