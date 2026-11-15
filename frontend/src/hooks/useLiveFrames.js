import { useEffect, useState } from 'react'
import { forEachConcurrent, loadFrameImage, loadFrames } from '../api.js'

// PNG downloads in flight at once. Each one can take ~10 s on the server.
const IMAGE_CONCURRENCY = 4

/**
 * Loads the frame list for `query`, then downloads every PNG and exposes the
 * frames as they arrive.
 *
 * status: 'idle' | 'searching' | 'loading' | 'done' | 'empty' | 'error'
 * frames: loaded frames only, in date order, each with a `src` object URL.
 *
 * `runKey` identifies one run (query + retry count). Changing it aborts the
 * previous run and revokes its object URLs.
 */
export default function useLiveFrames(query, runKey) {
  const [state, setState] = useState({ runKey: null })

  useEffect(() => {
    if (!query) return undefined

    const controller = new AbortController()
    const { signal } = controller
    const objectUrls = []
    const update = (patch) => {
      if (!signal.aborted) setState((prev) => ({ ...(prev.runKey === runKey ? prev : { runKey }), ...patch }))
    }

    async function run() {
      let list
      try {
        list = await loadFrames(query, { signal })
      } catch (err) {
        if (!signal.aborted) update({ status: 'error', error: err.message })
        return
      }

      if (list.frames.length === 0) {
        update({ status: 'empty' })
        return
      }

      const slots = list.frames.map((frame) => ({ ...frame, src: null }))
      let completed = 0
      update({ status: 'loading', total: slots.length, completed, frames: [] })

      await forEachConcurrent(slots, IMAGE_CONCURRENCY, async (slot) => {
        if (signal.aborted) return
        try {
          const { objectUrl, wavelengthUm } = await loadFrameImage(slot.url, { signal })
          objectUrls.push(objectUrl)
          slot.src = objectUrl
          slot.wavelength_um = wavelengthUm
        } catch {
          // A failed frame is skipped; the rest of the animation still loads.
        }
        completed += 1
        update({ completed, frames: slots.filter((s) => s.src).map((s) => ({ ...s })) })
      })

      if (signal.aborted) return
      if (objectUrls.length === 0) {
        update({ status: 'error', error: 'None of the images could be downloaded from the archive.' })
      } else {
        update({ status: 'done' })
      }
    }

    run()
    return () => {
      controller.abort()
      objectUrls.forEach((u) => URL.revokeObjectURL(u))
    }
  }, [query, runKey])

  if (!query) return { status: 'idle', frames: [] }
  // Until the new run reports anything, show the "searching" state rather
  // than leftovers from the previous query.
  if (state.runKey !== runKey) return { status: 'searching', frames: [] }
  return { frames: [], ...state }
}
