import { useEffect, useState } from 'react'
import { loadEpochs } from '../api.js'

/**
 * Loads epoch stacks once `ready` is true (after the animation finished
 * loading, so the server already has the cutouts cached).
 *
 * status: 'idle' | 'loading' | 'ready' | 'unavailable' | 'error'
 */
export default function useEpochs(query, runKey, ready) {
  const [state, setState] = useState({ runKey: null })

  useEffect(() => {
    if (!query || !ready) return undefined
    const controller = new AbortController()
    loadEpochs(query, { signal: controller.signal })
      .then((data) => {
        if (controller.signal.aborted) return
        setState(data ? { runKey, status: 'ready', data } : { runKey, status: 'unavailable' })
      })
      .catch((err) => {
        if (!controller.signal.aborted) setState({ runKey, status: 'error', error: err.message })
      })
    return () => controller.abort()
  }, [query, runKey, ready])

  if (!query || !ready) return { status: 'idle' }
  if (state.runKey !== runKey) return { status: 'loading' }
  return state
}
