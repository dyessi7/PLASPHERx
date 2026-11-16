import { useEffect, useState } from 'react'
import { loadTargets } from '../api.js'
import { SUGGESTED_TARGETS } from '../constants.js'

/**
 * Shortcut buttons that fill in the search form with a known object.
 * Synchronizes with /api/targets and marks the selected object.
 */
export default function TargetButtons({ onSelect, disabled, current }) {
  const [targets, setTargets] = useState(SUGGESTED_TARGETS)

  useEffect(() => {
    let active = true
    loadTargets().then((catalog) => {
      if (active && catalog.length > 0) {
        // Enrich static 2026-epoch coordinates with backend metadata without
        // overwriting proper-motion-adjusted coordinates for SPHEREx's epoch.
        const byName = new Map(catalog.map((c) => [c.name.toLowerCase(), c]))
        setTargets(
          SUGGESTED_TARGETS.map((t) => {
            const match = byName.get(t.name.toLowerCase())
            return match ? { ...t, id: match.id, description: match.description } : t
          }),
        )
      }
    })
    return () => {
      active = false
    }
  }, [])

  return (
    <section className="targets" aria-labelledby="targets-title">
      <h2 id="targets-title" className="section-title">
        Try a known target
      </h2>
      <div className="targets__list">
        {targets.map((t) => (
          <button
            key={t.id || t.name}
            type="button"
            className="button target-button"
            aria-pressed={Boolean(current && Math.abs(current.ra - t.ra) < 0.001 && Math.abs(current.dec - t.dec) < 0.001)}
            onClick={() => onSelect(t)}
            disabled={disabled}
            title={t.description || t.name}
          >
            {t.name}
          </button>
        ))}
      </div>
    </section>
  )
}
