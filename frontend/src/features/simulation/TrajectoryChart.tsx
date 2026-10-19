import { useState } from 'react'
import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { buildTrajectorySeries } from '@/domain/metrics'
import { STRATEGY_NAMES } from '@/domain/terminology'
import type { StrategyResult } from '@/domain/types'
import styles from './simulation.module.css'

export interface TrajectoryChartProps {
  ppo: StrategyResult
  baseline: StrategyResult
  selectedStep: number
  onSelectStep: (step: number) => void
}

const MEASURES = {
  resistantCount: { name: 'Resistant antibiotics', axis: 'Resistant (of 7)' },
  susceptibleCount: { name: 'Susceptible options', axis: 'Susceptible (of 7)' },
} as const

/**
 * Per-state counts returned by the API. It is the number of resistant (or susceptible) antibiotics at each step, not the
 * cumulative resistance burden, which the API reports only for the whole run.
 */
export function TrajectoryChart({ ppo, baseline, selectedStep, onSelectStep }: TrajectoryChartProps) {
  const [measure, setMeasure] = useState<keyof typeof MEASURES>('resistantCount')
  const points = buildTrajectorySeries(ppo, baseline, measure)
  const last = (key: 'ppo' | 'baseline') => points.filter((point) => point[key] !== null).at(-1)?.[key]

  return (
    <figure style={{ margin: 0 }} className="stack">
      <figcaption className="row" style={{ justifyContent: 'space-between' }}>
        <strong>{MEASURES[measure].name} by step</strong>
        <span role="group" aria-label="Chart measure" className="row">
          {(Object.keys(MEASURES) as Array<keyof typeof MEASURES>).map((key) => (
            <button key={key} type="button" className={styles['stepChip']} style={{ padding: '0 0.75rem', fontSize: 'var(--text-xs)' }} aria-pressed={measure === key} onClick={() => setMeasure(key)}>
              {key === 'resistantCount' ? 'Resistant' : 'Susceptible'}
            </button>
          ))}
        </span>
      </figcaption>
      <div className={styles['chartBox']}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={points}
            accessibilityLayer
            margin={{ top: 8, right: 12, bottom: 22, left: 0 }}
            onClick={(state) => {
              const step = Number(state?.activeLabel)
              if (Number.isInteger(step) && step >= 0) {
                onSelectStep(step)
              }
            }}
          >
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="step" type="number" domain={[0, 'dataMax']} allowDecimals={false} tick={{ fontSize: 12 }} label={{ value: 'Step', position: 'insideBottom', offset: -12, fontSize: 12 }} />
            <YAxis domain={[0, 7]} allowDecimals={false} tick={{ fontSize: 12 }} label={{ value: MEASURES[measure].axis, angle: -90, position: 'insideLeft', fontSize: 12 }} />
            <Tooltip />
            <Legend verticalAlign="top" height={28} />
            <ReferenceLine x={selectedStep} stroke="var(--color-text-muted)" strokeDasharray="2 2" />
            <Line type="monotone" dataKey="ppo" name={STRATEGY_NAMES.ppo} stroke="var(--color-series-ppo)" strokeWidth={2.5} dot={{ r: 3 }} connectNulls={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="baseline" name="Baseline" stroke="var(--color-series-baseline)" strokeWidth={2.5} strokeDasharray="6 3" dot={{ r: 3 }} connectNulls={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="visually-hidden">
        {MEASURES[measure].name}. {STRATEGY_NAMES.ppo} ends at {last('ppo')}; Random Susceptible Baseline ends at {last('baseline')}. Select a step on the chart or the timeline to inspect it.
      </p>
    </figure>
  )
}
