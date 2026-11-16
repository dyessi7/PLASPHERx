import { useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import '../styles/sheet.css'

/**
 * Footer link that opens a floating sheet centered on screen.
 * Closes with the x button, Escape, or a click outside.
 */
function InfoSheet({ label, title, children }) {
  const [open, setOpen] = useState(false)
  const closeRef = useRef(null)
  const openerRef = useRef(null)
  const id = useId()

  // Escape closes; focus moves into the sheet on open and back on close.
  useEffect(() => {
    if (!open) return undefined
    closeRef.current?.focus()
    const opener = openerRef.current
    function onKey(e) {
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
      opener?.focus()
    }
  }, [open])

  return (
    <>
      <button
        ref={openerRef}
        type="button"
        className="sheet-link"
        aria-expanded={open}
        aria-controls={`${id}-sheet`}
        onClick={() => setOpen(true)}
      >
        {label}
      </button>

      {createPortal(
        <>
          <div className={`sheet-backdrop ${open ? 'is-open' : ''}`} onClick={() => setOpen(false)} aria-hidden="true" />

          <aside
            id={`${id}-sheet`}
            className={`sheet ${open ? 'is-open' : ''}`}
            role="dialog"
            aria-modal="true"
            aria-labelledby={`${id}-title`}
            inert={!open}
          >
            <div className="sheet__head">
              <h2 id={`${id}-title`}>{title}</h2>
              <button ref={closeRef} type="button" className="sheet__close" onClick={() => setOpen(false)} aria-label="Close">
                ×
              </button>
            </div>

            <div className="sheet__body">{children}</div>
          </aside>
        </>,
        document.body,
      )}
    </>
  )
}

export function AboutSheet() {
  return (
    <InfoSheet label="About" title="About">
      <section className="sheet__section">
        <h3>The project</h3>
        <p>
          PLASPHEREx shows how a patch of sky changes over time in the infrared images taken by NASA&apos;s SPHEREx space
          telescope. SPHEREx scans the whole sky again and again, so the same spot is photographed many times. Played in
          order, those images reveal stars and objects that move or change brightness.
        </p>
        <p>
          Built by team VTG for the NASA Space Apps Challenge 2026, challenge &ldquo;Planet X and SPHEREx&rdquo;. All
          images come live from the NASA/IPAC Infrared Science Archive (IRSA).
        </p>
      </section>

      <section className="sheet__section">
        <h3>How to use</h3>
        <p>
          <b>First</b>, type a sky position in the panel on the left: RA and Dec in degrees (or sexagesimal, e.g.{' '}
          <code>08h55m10s</code>) and a field of view. <b>Then</b>, pick a detector; each one covers a different infrared
          band, from D1 (≈0.75 µm) to D6 (≈5 µm). <b>Finally</b>, press <i>Show images</i>, or simply click one of the
          known targets to fill everything in at once.
        </p>
      </section>

      <section className="sheet__section">
        <h3>What you see</h3>
        <p>
          <b>Frames</b> plays every SPHEREx image of that spot in date order, as an animation; use play, the arrows or
          the bar under the image to move between them. <b>Epochs</b> combines the frames from each observing period
          into one sharper image, and its <b>differences</b> subtract an earlier epoch from a later one: gray means no
          change, white brighter, black fainter. <b>Spectrum</b> measures the target&apos;s brightness at each wavelength
          across the six detectors; hollow points are saturated, so their value is a lower limit.
        </p>
      </section>
    </InfoSheet>
  )
}
