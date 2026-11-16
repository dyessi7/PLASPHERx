import { useEffect, useMemo, useRef, useState } from 'react'
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

// Four corner arrows: pointing out to expand, pointing in to exit full screen.
const EXPAND_PATH = 'M10 10L4 4M4 9V4h5M14 10l6-6M15 4h5v5M10 14l-6 6M4 15v5h5M14 14l6 6M20 15v5h-5'
const COLLAPSE_PATH = 'M4 4l6 6M5 10h5V5M20 4l-6 6M19 10h-5V5M4 20l6-6M5 14h5v5M20 20l-6-6M19 14h-5v5'

function FullscreenIcon({ active }) {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">
      <path
        d={active ? COLLAPSE_PATH : EXPAND_PATH}
        fill="none"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
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
  const viewportRef = useRef(null)
  const [fullscreen, setFullscreen] = useState(false)
  const canFullscreen = typeof document !== 'undefined' && document.fullscreenEnabled

  useEffect(() => {
    const onChange = () => setFullscreen(document.fullscreenElement === viewportRef.current)
    document.addEventListener('fullscreenchange', onChange)
    return () => document.removeEventListener('fullscreenchange', onChange)
  }, [])

  const toggleFullscreen = () => {
    if (document.fullscreenElement) document.exitFullscreen()
    else viewportRef.current?.requestFullscreen().catch(() => {})
  }

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
        <div ref={viewportRef} className={`player__viewport ${zoom ? 'player__viewport--zoomed' : ''}`}>
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
          {canFullscreen && (
            <button
              type="button"
              className="player__expand"
              onClick={toggleFullscreen}
              aria-label={fullscreen ? 'Exit full screen' : 'Full screen'}
              title={fullscreen ? 'Exit full screen (Esc)' : 'Full screen'}
            >
              <FullscreenIcon active={fullscreen} />
            </button>
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

        <div className="player__tools" role="group" aria-label="Astronomer tools">
          <label
            className="player__check"
            title="Blink comparator: rapidly alternate between first and last frame to spot moving objects"
          >
            <input
              type="checkbox"
              checked={blink}
              onChange={(e) => {
                setBlink(e.target.checked)
                if (e.target.checked && !playing) setPlaying(true)
              }}
            />
            Blink (1 ↔ {count})
          </label>
          <label
            className="player__check"
            title="Invert colormap: negative mode (black stars on light background) for high contrast"
          >
            <input type="checkbox" checked={inverted} onChange={(e) => setInverted(e.target.checked)} />
            Negative
          </label>
          <label className="player__check" title="Toggle central celestial crosshair">
            <input type="checkbox" checked={reticle} onChange={(e) => setReticle(e.target.checked)} />
            Reticle
          </label>
          <label className="player__check" title="2x center magnification">
            <input type="checkbox" checked={zoom} onChange={(e) => setZoom(e.target.checked)} />
            2x Zoom
          </label>
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
