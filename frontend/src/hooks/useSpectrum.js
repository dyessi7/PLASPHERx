import { useCallback, useEffect, useRef, useState } from 'react'
import { forEachConcurrent, loadSpectrum } from '../api.js'
import { DETECTOR_IDS } from '../constants.js'

const SPECTRUM_CONCURRENCY = 2

/**
 * Builds a spectrum on demand by querying every detector, two at a time.
 * Points are added as each detector answers; failed detectors are skipped.
 *
 * status: 'idle' | 'loading' | 'done' | 'unavailable' | 'error'
 * 'unavailable' means every detector answered 404/501 (endpoint not ready).
 */
export default function useSpectrum(query, runKey) {
  const [state, setState] = useState({ runKey: null })
  const controllerRef = useRef(null)

  // Abort an in-flight build when the query changes or on unmount.
  useEffect(() => () => controllerRef.current?.abort(), [runKey])

  const build = useCallback(async () => {
    if (!query) return
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    const { signal } = controller

    const result = {
      runKey,
      status: 'loading',
      total: DETECTOR_IDS.length,
      completed: 0,
      points: [],
      failed: [],
      unavailable: 0,
      fluxUnit: null,
      apertureArcsec: null,
    }
    setState({ ...result })

    await forEachConcurrent(DETECTOR_IDS, SPECTRUM_CONCURRENCY, async (detector) => {
      if (signal.aborted) return
      try {
        const data = await loadSpectrum({ ...query, detector }, { signal })
        if (data === null) {
          result.unavailable += 1
        } else {
          result.points = result.points.concat(data.points.map((p) => ({ ...p, detector: p.detector || detector })))
          result.fluxUnit ??= data.flux_unit ?? null
          result.apertureArcsec ??= data.aperture_arcsec ?? null
        }
      } catch {
        if (signal.aborted) return
        result.failed = [...result.failed, detector]
      }
      result.completed += 1
      if (!signal.aborted) setState({ ...result })
    })

    if (signal.aborted) return
    if (result.unavailable === result.total) result.status = 'unavailable'
    else if (result.points.length === 0) result.status = 'error'
    else result.status = 'done'
    setState({ ...result })
  }, [query, runKey])

  if (!query || state.runKey !== runKey) return { status: 'idle', points: [], build }
  return { ...state, build }
}
