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

const AXIS_COLOR = '#a1a1a1'
const GRID_COLOR = '#262626'

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
        Flux {p.saturated && '≥ '}
        {formatNumber(p.flux, 4)}
        {p.flux_err != null && ` ± ${formatNumber(p.flux_err, 2)}`} {unit}
      </div>
      {p.saturated && <div>Saturated: lower limit</div>}
    </div>
  )
}

/**
 * Saturated points are lower limits (the brightest pixels could not be
 * measured), so they are drawn hollow instead of filled.
 */
function SpectrumDot({ cx, cy, fill, payload }) {
  if (cx == null || cy == null) return null
  return payload?.saturated ? (
    <circle cx={cx} cy={cy} r={4} fill="#0a0a0a" stroke={fill} strokeWidth={2} />
  ) : (
    <circle cx={cx} cy={cy} r={5} fill={fill} stroke="#0a0a0a" strokeWidth={2} />
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

  const anySaturated = points.some((p) => p.saturated)
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
                  formatter={(value) => <span style={{ color: '#ededed' }}>{value}</span>}
                />
                {series.map((s) => (
                  <Scatter
                    key={s.id}
                    name={s.id}
                    data={s.points}
                    fill={DETECTOR_COLORS[s.id]}
                    shape={SpectrumDot}
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

          {anySaturated && (
            <p className="section-hint">
              Hollow points are saturated: the star was too bright for the detector, so their flux is a lower limit.
            </p>
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
                  <th scope="col">Saturated</th>
                </tr>
              </thead>
              <tbody>
                {[...points]
                  .sort((a, b) => a.wavelength_um - b.wavelength_um)
                  .map((p, i) => (
                    <tr key={i}>
                      <td>{p.detector}</td>
                      <td className="mono">{formatNumber(p.wavelength_um, 4)}</td>
                      <td className="mono">
                        {p.saturated && '≥ '}
                        {formatNumber(p.flux, 4)}
                      </td>
                      <td className="mono">{p.flux_err != null ? formatNumber(p.flux_err, 2) : '—'}</td>
                      <td className="mono">{p.mjd != null ? p.mjd.toFixed(2) : '—'}</td>
                      <td>{p.saturated ? 'Yes (lower limit)' : 'No'}</td>
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
