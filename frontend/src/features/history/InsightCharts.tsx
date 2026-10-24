import { useState } from 'react'
import {
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts'
import { STRATEGY_COLORS, strategyLabel } from '@/domain/terminology'
import { shortId } from '@/domain/formatters'
import type { SavedAnalysis } from './history-api'
import { INSIGHT_POLICIES, policyResult, summarizeEvidence } from './insight-data'
import styles from './insights.module.css'

const tooltipStyle = {
  background: 'var(--color-surface)',
  border: '1px solid var(--color-border)',
  color: 'var(--color-text)',
  borderRadius: 6,
  fontSize: 12,
}
const chartMetrics = {
  cumulativeResistanceBurden: 'Resistance burden',
  resistanceEmergenceEvents: 'Resistance emergence',
  finalSusceptibleCount: 'Remaining susceptible options',
  unsupportedStepCount: 'Unsupported steps',
} as const
export type InsightMetric = keyof typeof chartMetrics

export function InsightCharts({
  records,
  onInspect,
}: {
  records: SavedAnalysis[]
  onInspect: (id: string) => void
}) {
  const [view, setView] = useState<'records' | 'resistance'>('records')
  const [metric, setMetric] = useState<InsightMetric>('cumulativeResistanceBurden')
  const summary = summarizeEvidence(records)
  const points = [...records]
    .sort((a, b) => a.createdAtUtc.localeCompare(b.createdAtUtc))
    .map((run, index) => ({
      id: run.id,
      order: index + 1,
      label: shortId(run.id),
      date: new Date(run.createdAtUtc).toLocaleDateString(),
      profile: run.initialProfile.join(''),
      initialResistance: run.initialProfile.reduce<number>((sum, state) => sum + state, 0),
      ...Object.fromEntries(
        INSIGHT_POLICIES.map((policy) => [
          policy,
          policyResult(run, policy)?.metrics[metric] ?? null,
        ]),
      ),
    }))
  return (
    <div className={styles.chartGrid}>
      <section className={styles.panel} aria-labelledby="outcomes-heading">
        <div className={styles.panelHeading}>
          <div>
            <h2 id="outcomes-heading">Policy outcomes</h2>
            <p>One point per saved analysis. Select a point to inspect it.</p>
          </div>
          <label className={styles.metricLabel}>
            Metric
            <select
              value={metric}
              onChange={(event) => setMetric(event.target.value as InsightMetric)}
            >
              {Object.entries(chartMetrics).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className={styles.chartTabs} role="group" aria-label="Outcome chart view">
          <button
            type="button"
            aria-pressed={view === 'records'}
            onClick={() => setView('records')}
          >
            Across analyses
          </button>
          <button
            type="button"
            aria-pressed={view === 'resistance'}
            onClick={() => setView('resistance')}
          >
            Starting resistance
          </button>
        </div>
        <div className={styles.chartBody}>
          <ResponsiveContainer width="100%" height={280}>
            {view === 'records' ? (
              <LineChart
                data={points}
                margin={{ left: 0, right: 20, top: 15, bottom: 5 }}
                accessibilityLayer
              >
                <CartesianGrid vertical={false} stroke="var(--color-border)" />
                <XAxis
                  dataKey="order"
                  tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }}
                  label={{
                    value: 'Saved analyses · chronological order',
                    position: 'insideBottom',
                    offset: -3,
                    fontSize: 11,
                    fill: 'var(--color-text-muted)',
                  }}
                  height={45}
                  allowDecimals={false}
                />
                <YAxis
                  tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }}
                  width={36}
                  allowDecimals={metric === 'cumulativeResistanceBurden'}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  labelFormatter={(_, payload) => {
                    const point = payload[0]?.payload as (typeof points)[number] | undefined
                    return point ? `${point.date} · ${point.profile} · ${point.label}` : ''
                  }}
                />
                <Legend />
                {INSIGHT_POLICIES.map((policy) => (
                  <Line
                    key={policy}
                    dataKey={policy}
                    name={strategyLabel(policy)}
                    stroke={STRATEGY_COLORS[policy]}
                    strokeWidth={2}
                    type="linear"
                    connectNulls={false}
                    isAnimationActive={false}
                    strokeDasharray={policy === 'dqn' ? '5 3' : undefined}
                    dot={(props) => {
                      const point = props as { cx?: number; cy?: number; payload?: { id?: string } }
                      const id = point.payload?.id
                      if (
                        typeof point.cx !== 'number' ||
                        typeof point.cy !== 'number' ||
                        !Number.isFinite(point.cy)
                      )
                        return <g key={`${policy}-${id}-missing`} />
                      return (
                        <circle
                          key={`${policy}-${id}`}
                          cx={point.cx}
                          cy={point.cy}
                          r={4}
                          fill={STRATEGY_COLORS[policy]}
                          tabIndex={0}
                          role="button"
                          aria-label={`Inspect ${strategyLabel(policy)} point ${id ?? ''}`}
                          onClick={() => {
                            if (id) onInspect(id)
                          }}
                          onKeyDown={(event) => {
                            if (id && (event.key === 'Enter' || event.key === ' ')) {
                              event.preventDefault()
                              onInspect(id)
                            }
                          }}
                        />
                      )
                    }}
                  />
                ))}
              </LineChart>
            ) : (
              <ScatterChart margin={{ left: 0, right: 20, top: 15, bottom: 5 }} accessibilityLayer>
                <CartesianGrid stroke="var(--color-border)" />
                <XAxis
                  dataKey="initialResistance"
                  type="number"
                  domain={[0, 7]}
                  ticks={[0, 1, 2, 3, 4, 5, 6, 7]}
                  name="Initially resistant"
                  tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }}
                  label={{
                    value: 'Initially resistant antibiotics (of 7)',
                    position: 'insideBottom',
                    offset: -3,
                    fontSize: 11,
                    fill: 'var(--color-text-muted)',
                  }}
                  height={45}
                />
                <YAxis
                  dataKey="value"
                  name={chartMetrics[metric]}
                  type="number"
                  width={36}
                  tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }}
                />
                <ZAxis range={[45, 45]} />
                <Tooltip contentStyle={tooltipStyle} cursor={{ strokeDasharray: '3 3' }} />
                <Legend />
                {INSIGHT_POLICIES.map((policy) => (
                  <Scatter
                    key={policy}
                    name={strategyLabel(policy)}
                    fill={STRATEGY_COLORS[policy]}
                    isAnimationActive={false}
                    data={points.flatMap((point) => {
                      const value = point[policy as keyof typeof point]
                      return typeof value === 'number' ? [{ ...point, value }] : []
                    })}
                    onClick={(point) => {
                      const payload = point.payload as { id?: string }
                      if (payload.id) onInspect(payload.id)
                    }}
                  />
                ))}
              </ScatterChart>
            )}
          </ResponsiveContainer>
        </div>
        <p className={styles.chartNote}>
          {view === 'records'
            ? 'Lines connect recorded values, not a learning curve or an estimate of policy improvement.'
            : 'Repeated points may overlap. These are individual records, without pooled averages.'}{' '}
          Missing policies remain gaps.
        </p>
      </section>
      <section className={styles.panel} aria-labelledby="coverage-heading">
        <div className={styles.panelHeading}>
          <div>
            <h2 id="coverage-heading">Evidence coverage</h2>
            <p>What can these records support?</p>
          </div>
        </div>
        <div className={styles.rings}>
          <Donut
            label="Three-policy comparisons"
            value={summary.paired.length}
            total={records.length}
            color="var(--color-series-dqn)"
            unit="analyses"
          />
          <Donut
            label="Applicable transition data"
            value={summary.totalSteps - summary.unsupported}
            total={summary.totalSteps}
            color="var(--color-series-ppo)"
            unit="recorded steps"
          />
        </div>
        <div className={styles.coverageFoot}>
          <span>
            <i style={{ background: 'var(--color-series-dqn)' }} />
            {summary.paired.length} verified comparisons include all three policies
          </span>
          <span>
            <i style={{ background: 'var(--color-warning-solid)' }} />
            {summary.unsupported} steps lack applicable transition data
          </span>
        </div>
      </section>
    </div>
  )
}

function Donut({
  label,
  value,
  total,
  color,
  unit,
}: {
  label: string
  value: number
  total: number
  color: string
  unit: string
}) {
  return (
    <div className={styles.donut} role="img" aria-label={`${label}: ${value} of ${total} ${unit}`}>
      <div className={styles.ring}>
        <ResponsiveContainer width="100%" height={130}>
          <PieChart>
            <Pie
              data={total ? [{ value }, { value: total - value }] : [{ value: 1 }]}
              dataKey="value"
              innerRadius={45}
              outerRadius={56}
              startAngle={90}
              endAngle={-270}
              stroke="none"
              isAnimationActive={false}
            >
              <Cell fill={total ? color : 'var(--color-border)'} />
              <Cell fill="var(--color-border)" />
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <span className={styles.ringValue}>
          {total ? Math.round((value / total) * 100) : '—'}
          <small>{total ? '%' : ''}</small>
        </span>
      </div>
      <strong>{label}</strong>
      <span>
        {value} / {total} {unit}
      </span>
    </div>
  )
}
