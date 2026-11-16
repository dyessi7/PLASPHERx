import DetectorSelect from './DetectorSelect.jsx'
import '../styles/form.css'

const FIELDS = [
  { name: 'ra', label: 'RA', unit: '°', hint: '0 to 360' },
  { name: 'dec', label: 'Dec', unit: '°', hint: '−90 to 90' },
  { name: 'fov', label: 'Field of view', unit: '°', hint: '0.02 to 0.5' },
]

/**
 * Sky coordinate search. Values are kept as strings by the parent so the user
 * can type freely; validation happens on submit.
 */
export default function SearchForm({ form, errors, onFieldChange, onSubmit, disabled }) {
  return (
    <form
      className="search-form panel"
      noValidate
      onSubmit={(e) => {
        e.preventDefault()
        onSubmit()
      }}
    >
      <h2 className="section-title">Search the sky by coordinates</h2>
      <p className="section-hint">Decimal degrees or sexagesimal (e.g. 08h55m10s, −07d14m42s).</p>

      {disabled && (
        <p className="status status--error" role="alert">
          The data service is not configured.
        </p>
      )}

      <div className="search-form__grid">
        {FIELDS.map((f) => {
          const error = errors[f.name]
          const id = `field-${f.name}`
          return (
            <div className="field" key={f.name}>
              <label htmlFor={id}>
                {f.label} <span className="field__unit">({f.unit})</span>
              </label>
              <input
                id={id}
                type="text"
                inputMode="decimal"
                autoComplete="off"
                spellCheck="false"
                value={form[f.name]}
                onChange={(e) => onFieldChange(f.name, e.target.value)}
                aria-invalid={error ? 'true' : undefined}
                aria-describedby={`${id}-msg`}
                placeholder={f.name === 'fov' ? undefined : f.hint}
                disabled={disabled}
              />
              <span id={`${id}-msg`} className={error ? 'field__error' : 'field__hint'}>
                {error || f.hint}
              </span>
            </div>
          )
        })}

        <div className="field">
          <label htmlFor="field-detector">Detector</label>
          <DetectorSelect
            id="field-detector"
            value={form.detector}
            onChange={(value) => onFieldChange('detector', value)}
            disabled={disabled}
          />
          <span className="field__hint">Wavelength band</span>
        </div>
      </div>

      <button type="submit" className="button button--primary" disabled={disabled}>
        Show images
      </button>
    </form>
  )
}
