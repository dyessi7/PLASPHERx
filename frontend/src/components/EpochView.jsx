import { useMemo, useState } from 'react'
import Player from './Player.jsx'

function epochLabel(epoch) {
  if (!epoch) return '?'
  return epoch.date_start === epoch.date_end ? epoch.date_start : `${epoch.date_start} – ${epoch.date_end}`
}

/**
 * Epoch stacks (many frames averaged per observing season) and the
 * differences between them. Image URLs are data URIs from the API.
 */
export default function EpochView({ data, coords }) {
  const hasDiffs = data.diffs.length > 0
  const [mode, setMode] = useState('epochs')
  const showDiffs = hasDiffs && mode === 'diffs'

  const epochFrames = useMemo(
    () =>
      data.epochs.map((e) => ({
        src: e.url,
        label: epochLabel(e),
        detector: data.detector,
        caption: `Epoch ${e.id}, ${e.n_frames} frames combined`,
      })),
    [data],
  )

  const diffFrames = useMemo(() => {
    const byId = Object.fromEntries(data.epochs.map((e) => [e.id, e]))
    return data.diffs.map((d) => ({
      src: d.url,
      label: `${epochLabel(byId[d.b])} minus ${epochLabel(byId[d.a])}`,
      detector: data.detector,
      caption: `Difference: epoch ${d.b} minus epoch ${d.a}`,
    }))
  }, [data])

  const frames = showDiffs ? diffFrames : epochFrames

  return (
    <div className="epochs">
      {hasDiffs ? (
        <div className="segmented" role="group" aria-label="Epoch display">
          <button type="button" aria-pressed={!showDiffs} onClick={() => setMode('epochs')}>
            Epoch images
          </button>
          <button type="button" aria-pressed={showDiffs} onClick={() => setMode('diffs')}>
            Differences
          </button>
        </div>
      ) : (
        <p className="status">Only one observing epoch is available for this position yet.</p>
      )}

      <p className="section-hint">
        {showDiffs
          ? 'Each image subtracts an earlier epoch from a later one.'
          : 'Each image combines all frames from one observing period.'}
      </p>

      <Player
        key={showDiffs ? 'diffs' : 'epochs'}
        frames={frames}
        autoPlay={false}
        describe={(f) => `${f.caption}, ${f.label}, SPHEREx image at ${coords}`}
      />

      {showDiffs && (
        <ul className="legend" aria-label="Difference image legend">
          <li>
            <span className="legend__swatch" style={{ background: '#808080' }} /> gray = no change
          </li>
          <li>
            <span className="legend__swatch" style={{ background: '#ffffff' }} /> white = brighter
          </li>
          <li>
            <span className="legend__swatch" style={{ background: '#000000' }} /> black = fainter
          </li>
        </ul>
      )}
    </div>
  )
}
