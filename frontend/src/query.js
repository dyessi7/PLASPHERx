// Search query helpers: form validation and sync with the page URL
// (?ra=&dec=&fov=&detector=).

import { DEFAULT_DETECTOR, DEFAULT_FOV, DETECTOR_IDS, FIELD_LIMITS } from './constants.js'

const EMPTY_FORM = { ra: '', dec: '', fov: String(DEFAULT_FOV), detector: DEFAULT_DETECTOR }

const FIELD_NAMES = { ra: 'RA', dec: 'Dec', fov: 'Field of view' }

function parseSexagesimal(name, rawText) {
  const clean = String(rawText ?? '').trim()
  if (clean === '') return NaN

  // 1. Direct decimal number
  const asNumber = Number(clean)
  if (Number.isFinite(asNumber)) {
    return asNumber
  }

  // 2. HMS format for RA: e.g. 08h55m10.831s or 8h 55m 10.8s
  const hmsMatch = clean.match(/^(\d+(?:\.\d+)?)\s*h\s*(\d+(?:\.\d+)?)\s*m\s*(\d+(?:\.\d+)?)\s*s?$/i)
  if (hmsMatch && name === 'ra') {
    const h = parseFloat(hmsMatch[1])
    const m = parseFloat(hmsMatch[2])
    const s = parseFloat(hmsMatch[3])
    return (h + m / 60 + s / 3600) * 15.0
  }

  // 3. DMS format: e.g. -7d14m42.53s or +30d24m05s
  const dmsMatch = clean.match(/^([+-]?\d+(?:\.\d+)?)\s*d\s*(\d+(?:\.\d+)?)\s*m\s*(\d+(?:\.\d+)?)\s*s?$/i)
  if (dmsMatch) {
    const sign = clean.startsWith('-') ? -1 : 1
    const d = Math.abs(parseFloat(dmsMatch[1]))
    const m = parseFloat(dmsMatch[2])
    const s = parseFloat(dmsMatch[3])
    return sign * (d + m / 60 + s / 3600)
  }

  // 4. Colon-separated or space-separated: e.g. "08:55:10.83" or "-07:14:42.5" or "08 55 10.83"
  const parts = clean.split(/[:\s]+/).filter(Boolean)
  if (parts.length === 3 && parts.every((p) => Number.isFinite(Number(p)))) {
    const sign = clean.startsWith('-') ? -1 : 1
    const p0 = Math.abs(parseFloat(parts[0]))
    const p1 = parseFloat(parts[1])
    const p2 = parseFloat(parts[2])
    const total = p0 + p1 / 60 + p2 / 3600
    if (name === 'ra') {
      return total * 15.0 // Convert hours to degrees for RA
    }
    return sign * total
  }

  return NaN
}

function parseField(name, raw) {
  const text = String(raw ?? '').trim()
  const { min, max } = FIELD_LIMITS[name]
  if (text === '') return { error: `${FIELD_NAMES[name]} is required.` }
  const parsed = name === 'fov' ? Number(text) : parseSexagesimal(name, text)
  if (!Number.isFinite(parsed)) return { error: `${FIELD_NAMES[name]} must be valid decimal degrees or sexagesimal (e.g. 08h55m10s).` }
  const value = Math.round(parsed * 1e5) / 1e5
  if (value < min || value > max) return { error: `${FIELD_NAMES[name]} must be between ${min} and ${max}.` }
  return { value }
}

/**
 * Validates form values. Returns { errors, query }, where `query` is null
 * unless every field is valid.
 */
export function validateForm(form) {
  const errors = {}
  const query = {}
  for (const name of ['ra', 'dec', 'fov']) {
    const { value, error } = parseField(name, form[name])
    if (error) errors[name] = error
    else query[name] = value
  }
  query.detector = DETECTOR_IDS.includes(form.detector) ? form.detector : DEFAULT_DETECTOR
  return { errors, query: Object.keys(errors).length ? null : query }
}

/** Stable string identity for a query, used to reset state between searches. */
export function queryKey(query) {
  return query ? `${query.ra}|${query.dec}|${query.fov}|${query.detector}` : ''
}

/** Reads form values from the current page URL. Missing values use defaults. */
export function readFormFromUrl() {
  const params = new URLSearchParams(window.location.search)
  return {
    ra: params.get('ra') ?? EMPTY_FORM.ra,
    dec: params.get('dec') ?? EMPTY_FORM.dec,
    fov: params.get('fov') ?? EMPTY_FORM.fov,
    detector: DETECTOR_IDS.includes(params.get('detector')) ? params.get('detector') : EMPTY_FORM.detector,
  }
}

/** Replaces the page URL with the given query, without adding history entries. */
export function writeQueryToUrl(query) {
  const url = new URL(window.location.href)
  url.search = query
    ? new URLSearchParams({
        ra: String(query.ra),
        dec: String(query.dec),
        fov: String(query.fov),
        detector: query.detector,
      }).toString()
    : ''
  window.history.replaceState(null, '', url)
}
