import { SUGGESTED_TARGETS } from '../constants.js'

/**
 * Shortcut buttons that fill in the search form with a known object.
 * The one matching the current search is marked as selected.
 */
export default function TargetButtons({ onSelect, disabled, current }) {
  return (
    <section className="targets" aria-labelledby="targets-title">
      <h2 id="targets-title" className="section-title">
        Try a known target
      </h2>
      <div className="targets__list">
        {SUGGESTED_TARGETS.map((t) => (
          <button
            key={t.name}
            type="button"
            className="button target-button"
            aria-pressed={Boolean(current && current.ra === t.ra && current.dec === t.dec && current.fov === t.fov)}
            onClick={() => onSelect(t)}
            disabled={disabled}
          >
            {t.name}
          </button>
        ))}
      </div>
    </section>
  )
}
