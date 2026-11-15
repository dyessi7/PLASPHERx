// Data layer. Precomputed targets (static files under public/data/) and the live
// API both return the same shape, so the rest of the app never needs to know
// where the frames came from:
//
//   { target: { name, ra, dec, fov }, frames: [{ url, mjd, date, detector, wavelength_um }] }
//
// Every frame `url` returned from here is absolute and ready for an <img>.

const API_URL = (import.meta.env.VITE_API_URL || '').trim().replace(/\/+$/, '')

/** True when a live API base URL was configured at build time. */
export const LIVE_API_AVAILABLE = API_URL !== ''

const DATA_BASE = new URL(`${import.meta.env.BASE_URL}data/`, window.location.href)

/** Thrown when a precomputed target has no manifest for the requested detector. */
export class NoDataError extends Error {
  constructor(message = 'No data available for this target yet.') {
    super(message)
    this.name = 'NoDataError'
  }
}

/** Thrown by loadLive() when VITE_API_URL is not set. */
export class LiveUnavailableError extends Error {
  constructor(message = 'Live search is not available in this deployment.') {
    super(message)
    this.name = 'LiveUnavailableError'
  }
}

// Target keys become part of a file path, so only allow simple slugs.
const KEY_PATTERN = /^[a-z0-9_-]+$/i
const DETECTOR_PATTERN = /^D[1-6]$/

function targetBase(key) {
  if (!KEY_PATTERN.test(key)) throw new NoDataError(`Unknown target "${key}".`)
  return new URL(`${key}/`, DATA_BASE)
}

function checkDetector(detector) {
  if (!DETECTOR_PATTERN.test(detector)) throw new NoDataError(`Unknown detector "${detector}".`)
}

/**
 * Fetches a static JSON file. Returns null when the file does not exist.
 * Dev servers and SPA hosts often answer missing files with index.html and a
 * 200 status, so a non-JSON response is also treated as "missing".
 */
async function fetchStaticJson(url, { signal } = {}) {
  const res = await fetch(url, { signal })
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`Could not load ${url.pathname || url} (HTTP ${res.status}).`)
  const type = res.headers.get('content-type') || ''
  if (!type.includes('json')) return null
  return res.json()
}

function resolveUrl(url, base) {
  return new URL(url, base).href
}

/** Resolves frame URLs and sorts frames chronologically. */
function normalizeManifest(manifest, base) {
  const frames = (manifest.frames || [])
    .filter((f) => f && f.url)
    .map((f) => ({
      url: resolveUrl(f.url, base),
      mjd: f.mjd ?? null,
      date: f.date ?? null,
      detector: f.detector ?? null,
      wavelength_um: f.wavelength_um ?? null,
    }))
    .sort((a, b) => (a.mjd ?? 0) - (b.mjd ?? 0))
  return { target: manifest.target || null, frames }
}

/** List of precomputed example targets. Returns [] if targets.json is missing. */
export async function loadTargets({ signal } = {}) {
  const data = await fetchStaticJson(new URL('targets.json', DATA_BASE), { signal })
  return Array.isArray(data) ? data : []
}

/** Frames for a precomputed target and detector. Throws NoDataError if absent. */
export async function loadPrecomputed(key, detector = 'D2', { signal } = {}) {
  checkDetector(detector)
  const base = targetBase(key)
  const manifest = await fetchStaticJson(new URL(`manifest_${detector}.json`, base), { signal })
  if (!manifest) throw new NoDataError()
  return normalizeManifest(manifest, base)
}

/**
 * Frames for any sky position, from the live API. Only the manifest is
 * fetched here; the PNGs themselves are slow and are loaded by the caller.
 */
export async function loadLive({ ra, dec, fov = 0.1, detector = 'D2', n = 16 }, { signal } = {}) {
  if (!LIVE_API_AVAILABLE) throw new LiveUnavailableError()

  const params = new URLSearchParams({
    ra: String(ra),
    dec: String(dec),
    fov: String(fov),
    detector,
    n: String(n),
  })
  const url = `${API_URL}/api/frames?${params}`

  let res
  try {
    res = await fetch(url, { signal })
  } catch (err) {
    if (err.name === 'AbortError') throw err
    throw new Error('Could not reach the SPHEREx Sky Viewer API. Check your connection and try again.', {
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
    throw new Error(`The archive request failed: ${detail}`)
  }
  if (!body || !Array.isArray(body.frames)) {
    throw new Error('The API returned an unexpected response.')
  }

  return normalizeManifest(body, `${API_URL}/`)
}

/** Epoch stacks and difference images. Returns null if not generated yet. */
export async function loadEpochs(key, detector = 'D2', { signal } = {}) {
  checkDetector(detector)
  const base = targetBase(key)
  const data = await fetchStaticJson(new URL(`epochs_${detector}.json`, base), { signal })
  if (!data) return null
  return {
    ...data,
    epochs: (data.epochs || []).map((e) => ({ ...e, url: resolveUrl(e.url, base) })),
    diffs: (data.diffs || []).map((d) => ({ ...d, url: resolveUrl(d.url, base) })),
  }
}

/** Photometry across wavelengths. Returns null if not generated yet. */
export async function loadSpectrum(key, { signal } = {}) {
  const data = await fetchStaticJson(new URL('spectrum.json', targetBase(key)), { signal })
  if (!data || !Array.isArray(data.points)) return null
  return data
}
