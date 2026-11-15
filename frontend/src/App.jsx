// Top-level page: search form, suggested targets, and the result tabs.
// One flow only: coordinates -> /api/frames -> progressive animation.
// The current search is mirrored in the URL as ?ra=&dec=&fov=&detector=.

import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { API_CONFIGURED } from './api.js'
import { queryKey, readFormFromUrl, validateForm, writeQueryToUrl } from './query.js'
import useLiveFrames from './hooks/useLiveFrames.js'
import useEpochs from './hooks/useEpochs.js'
import useSpectrum from './hooks/useSpectrum.js'
import SearchForm from './components/SearchForm.jsx'
import TargetButtons from './components/TargetButtons.jsx'
import Player from './components/Player.jsx'
import EpochView from './components/EpochView.jsx'
import './styles/tabs.css'

// recharts is large; load it only when the Spectrum tab is opened.
const SpectrumChart = lazy(() => import('./components/SpectrumChart.jsx'))

function initialState() {
  const form = readFormFromUrl()
  const params = new URLSearchParams(window.location.search)
  if (!params.has('ra') && !params.has('dec')) return { form, errors: {}, query: null }
  const { errors, query } = validateForm(form)
  return { form, errors, query: API_CONFIGURED ? query : null }
}

const TAB_LABELS = { frames: 'Frames', epochs: 'Epochs', spectrum: 'Spectrum' }

function Placeholder({ children }) {
  return (
    <div className="player">
      <div className="player__viewport player__viewport--empty" role="status">
        {children}
      </div>
    </div>
  )
}

export default function App() {
  const [initial] = useState(initialState)
  const [form, setForm] = useState(initial.form)
  const [errors, setErrors] = useState(initial.errors)
  const [query, setQuery] = useState(initial.query)
  const [attempt, setAttempt] = useState(0)
  const [activeTab, setActiveTab] = useState('frames')

  const key = queryKey(query)
  const runKey = `${key}#${attempt}`

  const frames = useLiveFrames(query, runKey)
  const epochs = useEpochs(query, runKey, frames.status === 'done')
  const spectrum = useSpectrum(query, key)

  useEffect(() => {
    if (query) writeQueryToUrl(query)
  }, [query])

  function search(values) {
    const result = validateForm(values)
    setErrors(result.errors)
    if (!result.query || !API_CONFIGURED) return
    if (queryKey(result.query) === key) {
      // Same search again: only restart it if the last one failed.
      if (frames.status === 'error') setAttempt((a) => a + 1)
      return
    }
    setQuery(result.query)
    setActiveTab('frames')
  }

  function handleFieldChange(name, value) {
    const next = { ...form, [name]: value }
    setForm(next)
    setErrors((prev) => ({ ...prev, [name]: undefined }))
    // Switching detector re-runs the current search right away.
    if (name === 'detector' && query) search(next)
  }

  function handleTargetSelect(target) {
    const next = { ra: String(target.ra), dec: String(target.dec), fov: String(target.fov), detector: form.detector }
    setForm(next)
    search(next)
  }

  const playerFrames = useMemo(
    () =>
      frames.frames.map((f) => ({
        src: f.src,
        label: f.date,
        detector: f.detector,
        wavelength_um: f.wavelength_um,
      })),
    [frames.frames],
  )

  const coords = query ? `RA ${query.ra}°, Dec ${query.dec}°` : ''

  const tabs = ['frames']
  if (epochs.status === 'ready' || epochs.status === 'error') tabs.push('epochs')
  if (query && spectrum.status !== 'unavailable') tabs.push('spectrum')
  const tab = tabs.includes(activeTab) ? activeTab : 'frames'

  return (
    <>
      <header className="app-header">
        <div className="app-header__inner">
          <h1 className="app-title">SPHEREx Sky Viewer</h1>
          <p className="app-subtitle">See how a patch of sky changes over time in infrared.</p>
        </div>
      </header>

      <main className="app-main">
        <SearchForm
          form={form}
          errors={errors}
          onFieldChange={handleFieldChange}
          onSubmit={() => search(form)}
          disabled={!API_CONFIGURED}
        />

        <TargetButtons onSelect={handleTargetSelect} disabled={!API_CONFIGURED} />

        {query ? (
          <section className="results panel" aria-labelledby="results-title">
            <h2 id="results-title" className="results__title mono">
              {coords} · FOV {query.fov}° · {query.detector}
            </h2>

            {tabs.length > 1 && (
              <div className="tabs" role="tablist" aria-label="Result views">
                {tabs.map((t) => (
                  <button
                    key={t}
                    type="button"
                    role="tab"
                    id={`tab-${t}`}
                    aria-selected={tab === t}
                    aria-controls="tab-panel"
                    className="tabs__tab"
                    onClick={() => setActiveTab(t)}
                  >
                    {TAB_LABELS[t]}
                  </button>
                ))}
              </div>
            )}

            <div id="tab-panel" role={tabs.length > 1 ? 'tabpanel' : undefined} aria-labelledby={`tab-${tab}`}>
              {tab === 'frames' && (
                <FramesPanel
                  frames={frames}
                  playerFrames={playerFrames}
                  runKey={runKey}
                  coords={coords}
                  detector={query.detector}
                  onRetry={() => setAttempt((a) => a + 1)}
                />
              )}

              {tab === 'epochs' &&
                (epochs.status === 'ready' ? (
                  <EpochView key={runKey} data={epochs.data} coords={coords} />
                ) : (
                  <p className="status status--error" role="alert">
                    {epochs.error}
                  </p>
                ))}

              {tab === 'spectrum' && (
                <Suspense fallback={<p className="status">Loading chart…</p>}>
                  <SpectrumChart spectrum={spectrum} />
                </Suspense>
              )}
            </div>
          </section>
        ) : (
          API_CONFIGURED && (
            <p className="status">Enter sky coordinates above, or pick a known target, to see its images over time.</p>
          )
        )}
      </main>

      <footer className="app-footer">
        <div className="app-footer__inner">Data: SPHEREx, via NASA/IPAC Infrared Science Archive (IRSA)</div>
      </footer>
    </>
  )
}

function FramesPanel({ frames, playerFrames, runKey, coords, detector, onRetry }) {
  const { status, total, completed, error } = frames

  if (status === 'searching') {
    return <Placeholder>Searching the SPHEREx archive…</Placeholder>
  }

  if (status === 'empty') {
    return (
      <p className="status">
        No SPHEREx images were found at this position for detector {detector}. Try another detector or one of the
        known targets.
      </p>
    )
  }

  if (status === 'error') {
    return (
      <div className="status status--error" role="alert">
        <p className="status__message">{error}</p>
        <button type="button" className="button" onClick={onRetry}>
          Try again
        </button>
        <p className="status__hint">Or pick one of the known targets above.</p>
      </div>
    )
  }

  const skipped = status === 'done' ? total - playerFrames.length : 0

  return (
    <div className="frames">
      {status === 'loading' && (
        <p className="frames__progress" role="status" aria-live="polite">
          Loading frames from the SPHEREx archive… {completed} of {total}
        </p>
      )}

      {playerFrames.length > 0 ? (
        <Player
          key={runKey}
          frames={playerFrames}
          describe={(f) => `SPHEREx infrared image at ${coords}, detector ${f.detector}, observed ${f.label}`}
        />
      ) : (
        <Placeholder>Waiting for the first image…</Placeholder>
      )}

      {skipped > 0 && (
        <p className="section-hint">
          {skipped} of {total} images could not be loaded and were skipped.
        </p>
      )}
    </div>
  )
}
