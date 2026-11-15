import {
  CartesianGrid,
  ErrorBar,
  Legend,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts'
import { DETECTOR_COLORS, DETECTOR_IDS } from '../constants.js'

const AXIS_COLOR = '#9aa5b1'
const GRID_COLOR = '#2c343e'

function formatNumber(value, digits = 3) {
  return typeof value === 'number' ? value.toPrecision(digits) : '—'
}

function PointTooltip({ active, payload, unit }) {
  if (!active || !payload || !payload.length) return null
  const p = payload[0].payload
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip__title">
        <span className="legend__swatch" style={{ background: DETECTOR_COLORS[p.detector] }} /> {p.detector}
      </div>
      <div>λ {formatNumber(p.wavelength_um, 4)} µm</div>
      <div>
        Flux {formatNumber(p.flux, 4)}
        {p.flux_err != null && ` ± ${formatNumber(p.flux_err, 2)}`} {unit}
      </div>
    </div>
  )
}

/**
 * Spectrum panel: a "Build spectrum" button, progress while the six detectors
 * are queried, and a scatter plot of flux vs. wavelength colored by detector.
 */
export default function SpectrumChart({ spectrum }) {
  const { status, points, completed, total, failed = [], fluxUnit, apertureArcsec, build } = spectrum
  const unit = fluxUnit || ''
  const loading = status === 'loading'

  const series = DETECTOR_IDS.map((id) => ({ id, points: points.filter((p) => p.detector === id) })).filter(
    (s) => s.points.length > 0,
  )

  return (
    <div className="spectrum">
      <div className="spectrum__actions">
        <button type="button" className="button button--primary" onClick={build} disabled={loading}>
          {status === 'idle' ? 'Build spectrum' : 'Rebuild spectrum'}
        </button>
        <span className="section-hint">Queries all six detectors. Takes about a minute.</span>
      </div>

      {loading && (
        <p className="status" role="status" aria-live="polite">
          Measuring brightness at each wavelength… {completed} of {total} detectors
        </p>
      )}

      {status === 'error' && (
        <p className="status status--error" role="alert">
          The spectrum could not be built. None of the detectors returned data. Try again in a moment.
        </p>
      )}

      {status === 'done' && failed.length > 0 && (
        <p className="section-hint">No data from {failed.join(', ')}; showing the other detectors.</p>
      )}

      {series.length > 0 && (
        <>
          <div className="spectrum__chart">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 12, right: 16, bottom: 28, left: 12 }}>
                <CartesianGrid stroke={GRID_COLOR} strokeDasharray="0" />
                <XAxis
                  type="number"
                  dataKey="wavelength_um"
                  name="Wavelength"
                  domain={[0.7, 5.1]}
                  ticks={[1, 2, 3, 4, 5]}
                  stroke={AXIS_COLOR}
                  tick={{ fill: AXIS_COLOR, fontSize: 12 }}
                  label={{ value: 'Wavelength (µm)', position: 'bottom', offset: 10, fill: AXIS_COLOR, fontSize: 12 }}
                />
                <YAxis
                  type="number"
                  dataKey="flux"
                  name="Flux"
                  stroke={AXIS_COLOR}
                  tick={{ fill: AXIS_COLOR, fontSize: 12 }}
                  tickFormatter={(v) => formatNumber(v, 3)}
                  width={64}
                  label={{
                    value: unit ? `Flux (${unit})` : 'Flux',
                    angle: -90,
                    position: 'insideLeft',
                    fill: AXIS_COLOR,
                    fontSize: 12,
                    style: { textAnchor: 'middle' },
                  }}
                />
                <ZAxis range={[64, 64]} />
                <Tooltip content={<PointTooltip unit={unit} />} cursor={{ stroke: GRID_COLOR }} />
                <Legend
                  verticalAlign="top"
                  height={32}
                  formatter={(value) => <span style={{ color: '#e4e8ed' }}>{value}</span>}
                />
                {series.map((s) => (
                  <Scatter
                    key={s.id}
                    name={s.id}
                    data={s.points}
                    fill={DETECTOR_COLORS[s.id]}
                    stroke="#151a20"
                    strokeWidth={2}
                    isAnimationActive={false}
                  >
                    <ErrorBar dataKey="flux_err" direction="y" width={4} stroke={DETECTOR_COLORS[s.id]} />
                  </Scatter>
                ))}
              </ScatterChart>
            </ResponsiveContainer>
          </div>

          {apertureArcsec != null && (
            <p className="section-hint">Brightness measured in a {formatNumber(apertureArcsec, 3)} arcsec aperture.</p>
          )}

          <details className="spectrum__table">
            <summary>Show data table</summary>
            <table>
              <thead>
                <tr>
                  <th scope="col">Detector</th>
                  <th scope="col">Wavelength (µm)</th>
                  <th scope="col">Flux{unit && ` (${unit})`}</th>
                  <th scope="col">Error</th>
                  <th scope="col">MJD</th>
                </tr>
              </thead>
              <tbody>
                {[...points]
                  .sort((a, b) => a.wavelength_um - b.wavelength_um)
                  .map((p, i) => (
                    <tr key={i}>
                      <td>{p.detector}</td>
                      <td className="mono">{formatNumber(p.wavelength_um, 4)}</td>
                      <td className="mono">{formatNumber(p.flux, 4)}</td>
                      <td className="mono">{p.flux_err != null ? formatNumber(p.flux_err, 2) : '—'}</td>
                      <td className="mono">{p.mjd != null ? p.mjd.toFixed(2) : '—'}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </details>
        </>
      )}
    </div>
  )
}
