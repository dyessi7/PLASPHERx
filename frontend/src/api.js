// Data layer. Everything comes from the live API at VITE_API_URL.
//
//   GET /api/frames    -> { target, frames: [{ url, mjd, date, detector, wavelength_um }] }
//   GET <frame url>    -> PNG, optionally with an X-Wavelength-Um header
//   GET /api/epochs    -> { target, detector, epochs: [...], diffs: [...] }
//   GET /api/spectrum  -> { target, detector, flux_unit, aperture_arcsec, points: [...] }
//
// Errors come back as JSON { "error": "..." } with a 4xx/5xx status.

const API_URL = (import.meta.env.VITE_API_URL || '').trim().replace(/\/+$/, '')

/** True when a data service URL was configured at build time. */
export const API_CONFIGURED = API_URL !== ''

/** Thrown when VITE_API_URL is not set. */
class ApiNotConfiguredError extends Error {
  constructor() {
    super('The data service is not configured.')
    this.name = 'ApiNotConfiguredError'
  }
}

/** Error from the API, carrying the HTTP status (0 for network failures). */
class ApiError extends Error {
  constructor(message, status, options) {
    super(message, options)
    this.name = 'ApiError'
    this.status = status
  }
}

// Status codes that mean "this endpoint is not available yet".
const UNAVAILABLE_STATUSES = new Set([404, 501])

async function getJson(path, params, { signal } = {}) {
  if (!API_CONFIGURED) throw new ApiNotConfiguredError()

  const url = `${API_URL}${path}?${new URLSearchParams(params)}`
  let res
  try {
    res = await fetch(url, { signal })
  } catch (err) {
    if (err.name === 'AbortError') throw err
    throw new ApiError('Could not reach the data service. Check your connection and try again.', 0, {
      cause: err,
    })
  }

  let body = null
  try {
    body = await res.json()
  } catch {
    // Non-JSON body; handled below.
  }

  if (!res.ok) {
    const detail = body && body.error ? body.error : `HTTP ${res.status}`
    throw new ApiError(`The archive request failed: ${detail}`, res.status)
  }
  if (!body) throw new ApiError('The data service returned an unexpected response.', res.status)
  return body
}

function queryParams({ ra, dec, fov, detector }, n) {
  return { ra: String(ra), dec: String(dec), fov: String(fov), detector, n: String(n) }
}

/** Frame list for a sky position. Frame URLs are absolute and sorted by date. */
export async function loadFrames(query, { signal } = {}) {
  const body = await getJson('/api/frames', queryParams(query, 16), { signal })
  if (!Array.isArray(body.frames)) throw new ApiError('The data service returned an unexpected response.', 200)

  const frames = body.frames
    .filter((f) => f && f.url)
    .map((f) => ({
      url: new URL(f.url, `${API_URL}/`).href,
      mjd: f.mjd ?? null,
      date: f.date ?? null,
      detector: f.detector ?? null,
      wavelength_um: f.wavelength_um ?? null,
    }))
    .sort((a, b) => (a.mjd ?? 0) - (b.mjd ?? 0))
  return { target: body.target || null, frames }
}

/**
 * Downloads one frame PNG. Returns an object URL (the caller must revoke it)
 * and the wavelength from the X-Wavelength-Um header, or null if absent.
 */
export async function loadFrameImage(url, { signal } = {}) {
  const res = await fetch(url, { signal })
  if (!res.ok) throw new ApiError(`Frame request failed (HTTP ${res.status}).`, res.status)
  const blob = await res.blob()
  const header = res.headers.get('X-Wavelength-Um')
  const wavelength = header === null || header.trim() === '' ? NaN : Number(header)
  return {
    objectUrl: URL.createObjectURL(blob),
    wavelengthUm: Number.isFinite(wavelength) ? wavelength : null,
  }
}

/** Epoch stacks and difference images. Returns null if the endpoint is not available. */
export async function loadEpochs(query, { signal } = {}) {
  try {
    const body = await getJson('/api/epochs', queryParams(query, 16), { signal })
    return { ...body, epochs: body.epochs || [], diffs: body.diffs || [] }
  } catch (err) {
    if (err instanceof ApiError && UNAVAILABLE_STATUSES.has(err.status)) return null
    throw err
  }
}

/** Photometry for one detector. Returns null if the endpoint is not available. */
export async function loadSpectrum(query, { signal } = {}) {
  try {
    const body = await getJson('/api/spectrum', queryParams(query, 4), { signal })
    return { ...body, points: Array.isArray(body.points) ? body.points : [] }
  } catch (err) {
    if (err instanceof ApiError && UNAVAILABLE_STATUSES.has(err.status)) return null
    throw err
  }
}

/** Runs `worker` over `items`, at most `limit` at a time. */
export async function forEachConcurrent(items, limit, worker) {
  let next = 0
  async function lane() {
    while (next < items.length) {
      const item = items[next++]
      await worker(item)
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, lane))
}
