// Search query helpers: form validation and sync with the page URL
// (?ra=&dec=&fov=&detector=).

import { DEFAULT_DETECTOR, DEFAULT_FOV, DETECTOR_IDS, FIELD_LIMITS } from './constants.js'

const EMPTY_FORM = { ra: '', dec: '', fov: String(DEFAULT_FOV), detector: DEFAULT_DETECTOR }

const FIELD_NAMES = { ra: 'RA', dec: 'Dec', fov: 'Field of view' }

function parseField(name, raw) {
  const text = String(raw ?? '').trim()
  const { min, max } = FIELD_LIMITS[name]
  if (text === '') return { error: `${FIELD_NAMES[name]} is required.` }
  const value = Number(text)
  if (!Number.isFinite(value)) return { error: `${FIELD_NAMES[name]} must be a number in decimal degrees.` }
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
