import { DETECTORS } from '../constants.js'

/** Detector picker; each option shows its approximate wavelength range. */
export default function DetectorSelect({ id, value, onChange, disabled }) {
  return (
    <select id={id} value={value} onChange={(e) => onChange(e.target.value)} disabled={disabled}>
      {DETECTORS.map((d) => (
        <option key={d.id} value={d.id}>
          {d.id} · {d.min.toFixed(2)}–{d.max.toFixed(2)} µm
        </option>
      ))}
    </select>
  )
}
