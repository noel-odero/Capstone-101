import { useState } from 'react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { buildTrajectorySeries } from '@/domain/metrics'
import { STRATEGY_COLORS, strategyLabel } from '@/domain/terminology'
import type { StrategyResult } from '@/domain/types'
import styles from './simulation.module.css'

export interface TrajectoryChartProps {
  results: readonly StrategyResult[]
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
export function TrajectoryChart({ results, selectedStep, onSelectStep }: TrajectoryChartProps) {
  const [measure, setMeasure] = useState<keyof typeof MEASURES>('resistantCount')
  const points = buildTrajectorySeries(results, measure)
  const last = (key: string) => points.filter((point) => point[key] !== null).at(-1)?.[key]

  return (
    <figure style={{ margin: 0 }} className="stack">
      <figcaption className="row" style={{ justifyContent: 'space-between' }}>
        <strong>{MEASURES[measure].name} by step</strong>
        <span role="group" aria-label="Chart measure" className="row">
          {(Object.keys(MEASURES) as Array<keyof typeof MEASURES>).map((key) => (
            <button
              key={key}
              type="button"
              className={styles['stepChip']}
              style={{ padding: '0 0.75rem', fontSize: 'var(--text-xs)' }}
              aria-pressed={measure === key}
              onClick={() => setMeasure(key)}
            >
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
            <XAxis
              dataKey="step"
              type="number"
              domain={[0, 'dataMax']}
              allowDecimals={false}
              tick={{ fontSize: '0.75rem' }}
              label={{ value: 'Step', position: 'insideBottom', offset: -12, fontSize: '0.75rem' }}
            />
            <YAxis
              domain={[0, 7]}
              allowDecimals={false}
              tick={{ fontSize: '0.75rem' }}
              label={{
                value: MEASURES[measure].axis,
                angle: -90,
                position: 'insideLeft',
                fontSize: '0.75rem',
              }}
            />
            <Tooltip />
            <Legend verticalAlign="top" height={28} wrapperStyle={{ fontSize: '0.75rem' }} />
            <ReferenceLine
              x={selectedStep}
              stroke="var(--color-text-muted)"
              strokeDasharray="2 2"
            />
            {results.map((result, index) => (
              <Line
                key={result.strategy}
                type="stepAfter"
                dataKey={result.strategy}
                name={strategyLabel(result.strategy)}
                stroke={STRATEGY_COLORS[result.strategy]}
                strokeWidth={2.5}
                strokeDasharray={index === 0 ? undefined : index === 1 ? '3 3' : '6 3'}
                dot={{ r: 3 }}
                connectNulls={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="visually-hidden">
        {MEASURES[measure].name}.{' '}
        {results
          .map((result) => `${strategyLabel(result.strategy)} ends at ${last(result.strategy)}`)
          .join('; ')}
        . Select a step on the chart or timeline to inspect it.
      </p>
    </figure>
  )
}
