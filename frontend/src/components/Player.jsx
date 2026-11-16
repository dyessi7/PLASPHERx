import { useEffect, useMemo, useState } from 'react'
import '../styles/player.css'

const MIN_FPS = 1
const MAX_FPS = 10

function isTextEntry(el) {
  if (!el) return false
  const tag = el.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable
}

const ICON_PATHS = {
  play: 'M7 4.5v15l12-7.5z',
  pause: 'M6 4.5h4v15H6zM14 4.5h4v15h-4z',
  prev: 'M5 4.5h2.5v15H5zM19 4.5v15L8.5 12z',
  next: 'M16.5 4.5H19v15h-2.5zM5 4.5v15L15.5 12z',
}

function Icon({ name }) {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false">
      <path d={ICON_PATHS[name]} fill="currentColor" />
    </svg>
  )
}

function formatWavelength(um) {
  return um == null ? null : `${um.toFixed(3)} µm`
}

/**
 * Plays a sequence of sky images.
 *
 * frames: [{ src, label, detector?, wavelength_um? }]
 *   `label` is the main caption (usually the observation date).
 * describe(frame): text for the image alt attribute.
 */
export default function Player({ frames, describe, autoPlay = true }) {
  const [failed, setFailed] = useState(() => new Set())
  const [position, setPosition] = useState(0)
  const [playing, setPlaying] = useState(autoPlay)
  const [fps, setFps] = useState(4)
  const [blink, setBlink] = useState(false)
  const [inverted, setInverted] = useState(false)
  const [reticle, setReticle] = useState(false)
  const [zoom, setZoom] = useState(false)

  const playable = useMemo(() => frames.filter((f) => !failed.has(f.src)), [frames, failed])
  const count = playable.length
  const index = count ? Math.min(position, count - 1) : 0
  const frame = playable[index]

  const markFailed = (src) =>
    setFailed((prev) => (prev.has(src) ? prev : new Set(prev).add(src)))

  // Preload and decode every frame so playback does not flicker. A frame that
  // fails to load is dropped from the animation.
  useEffect(() => {
    const images = frames.map((f) => {
      const img = new Image()
      img.onerror = () => markFailed(f.src)
      img.src = f.src
      return img
    })
    return () => images.forEach((img) => (img.onerror = null))
  }, [frames])

  // Advance one frame per tick while playing. In blink mode, alternates between first and last frame.
  useEffect(() => {
    if (!playing || count < 2) return undefined
    const id = setTimeout(() => {
      if (blink) {
        setPosition((i) => (i === 0 ? count - 1 : 0))
      } else {
        setPosition((i) => (Math.min(i, count - 1) + 1) % count)
      }
    }, 1000 / fps)
    return () => clearTimeout(id)
  }, [playing, fps, count, index, blink])

  const step = (delta) => {
    if (!count) return
    setPlaying(false)
    setPosition((i) => (Math.min(i, count - 1) + delta + count) % count)
  }

  // Keyboard: space = play/pause, arrows = step. Ignored while typing.
  useEffect(() => {
    function onKey(e) {
      if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey || isTextEntry(e.target)) return
      if (e.key === ' ' || e.code === 'Space') {
        // A focused button already toggles itself on space.
        if (e.target.tagName === 'BUTTON') return
        e.preventDefault()
        setPlaying((p) => !p)
      } else if (e.key === 'ArrowRight') {
        e.preventDefault()
        step(1)
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault()
        step(-1)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  if (!frame) {
    return (
      <div className="player">
        <div className="player__viewport player__viewport--empty">No images to show.</div>
      </div>
    )
  }

  const wavelength = formatWavelength(frame.wavelength_um)

  return (
    <div className="player player--split">
      <div className="player__stage">
        <div className={`player__viewport ${zoom ? 'player__viewport--zoomed' : ''}`}>
          <img
            className={`player__image ${inverted ? 'player__image--inverted' : ''} ${zoom ? 'player__image--zoomed' : ''}`}
            src={frame.src}
            alt={describe ? describe(frame) : frame.label || 'Sky image'}
            onError={() => markFailed(frame.src)}
            draggable="false"
          />
          {reticle && (
            <div className="player__reticle" aria-hidden="true">
              <span className="player__reticle-circle" />
            </div>
          )}
        </div>

        <dl className="player__info">
          <div>
            <dt>Date</dt>
            <dd>{frame.label || '—'}</dd>
          </div>
          {frame.detector && (
            <div>
              <dt>Detector</dt>
              <dd>{frame.detector}</dd>
            </div>
          )}
          {wavelength && (
            <div>
              <dt>Wavelength</dt>
              <dd>{wavelength}</dd>
            </div>
          )}
          {frame.saturated && (
            <div title="The star is brighter than the detector can measure. The white core is saturated, not a measured value.">
              <dt>Core</dt>
              <dd className="player__saturated">Saturated</dd>
            </div>
          )}
          {frame.flags && frame.flags.length > 0 && (
            <div title="Instrument contamination flags detected in aperture">
              <dt>Flags</dt>
              <dd className="player__flag-badge">{frame.flags.join(', ')}</dd>
            </div>
          )}
        </dl>

        <div className="player__controls">
          <button type="button" className="icon-button" onClick={() => step(-1)} aria-label="Previous frame" disabled={count < 2}>
            <Icon name="prev" />
          </button>
          <button
            type="button"
            className="icon-button icon-button--primary"
            onClick={() => setPlaying((p) => !p)}
            aria-label={playing ? 'Pause' : 'Play'}
            disabled={count < 2}
          >
            <Icon name={playing ? 'pause' : 'play'} />
          </button>
          <button type="button" className="icon-button" onClick={() => step(1)} aria-label="Next frame" disabled={count < 2}>
            <Icon name="next" />
          </button>

          <input
            type="range"
            className="player__scrubber"
            min="0"
            max={Math.max(count - 1, 0)}
            value={index}
            onChange={(e) => {
              setPlaying(false)
              setPosition(Number(e.target.value))
            }}
            aria-label="Frame position"
            disabled={count < 2}
          />

          <span className="player__counter mono" aria-live="off">
            {index + 1} / {count}
          </span>
        </div>
      </div>

      <div className="player__side">
        <label className="player__speed">
          <span>Speed</span>
          <input
            type="range"
            min={MIN_FPS}
            max={MAX_FPS}
            value={fps}
            onChange={(e) => setFps(Number(e.target.value))}
            aria-valuetext={`${fps} frames per second`}
          />
          <span className="mono">{fps} fps</span>
        </label>

        <div className="player__tools" role="toolbar" aria-label="Astronomer Tools">
          <button
            type="button"
            className="player__tool-button"
            aria-pressed={blink}
            onClick={() => {
              setBlink((b) => !b)
              if (!playing) setPlaying(true)
            }}
            title="Blink comparator: rapidly alternate between first and last frame to spot moving objects"
          >
            {blink ? 'Blinking (1 ↔ ' + count + ')' : 'Blink (1 ↔ ' + count + ')'}
          </button>
          <button
            type="button"
            className="player__tool-button"
            aria-pressed={inverted}
            onClick={() => setInverted((v) => !v)}
            title="Invert colormap: negative mode (black stars on light background) for high contrast"
          >
            Negative
          </button>
          <button
            type="button"
            className="player__tool-button"
            aria-pressed={reticle}
            onClick={() => setReticle((r) => !r)}
            title="Toggle central celestial crosshair"
          >
            Reticle
          </button>
          <button
            type="button"
            className="player__tool-button"
            aria-pressed={zoom}
            onClick={() => setZoom((z) => !z)}
            title="2x center magnification"
          >
            2x Zoom
          </button>
          <a
            href={frame.src}
            download={`spherex_${frame.detector || 'sky'}_frame_${index + 1}.png`}
            className="player__tool-button"
            title="Download current frame as PNG image"
          >
            Save PNG
          </a>
        </div>
      </div>
    </div>
  )
}
