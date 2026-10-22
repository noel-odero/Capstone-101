import { fixtures } from '@/test/fixtures/api-fixtures'
import { describe, expect, it } from 'vitest'
import {
  COMPARISON_METRIC_KEYS,
  METRIC_LABELS,
  UNAVAILABLE,
  buildMetricRows,
  buildTrajectorySeries,
  formatMetricValue,
} from './metrics'
import type { StrategyResult } from './types'

const { comparison } = fixtures
const ppo = comparison.ppo as StrategyResult
const baseline = comparison.baseline as StrategyResult

describe('metric formatting', () => {
  it('rounds fractional metrics for display only', () => {
    expect(formatMetricValue('cumulativeResistanceBurden', 2.4285714285714284)).toBe('2.43')
    expect(formatMetricValue('susceptibleActionRate', 1)).toBe('1.00')
  })

  it('shows counts as whole numbers and signs a change in susceptible options', () => {
    expect(formatMetricValue('finalResistantCount', 4)).toBe('4')
    expect(formatMetricValue('changeInSusceptibleCount', 2)).toBe('+2')
    expect(formatMetricValue('changeInSusceptibleCount', -3)).toBe('\u22123')
    expect(formatMetricValue('changeInSusceptibleCount', 0)).toBe('0')
  })

  it('never turns a missing value into zero', () => {
    expect(formatMetricValue('susceptibleActionRate', null)).toBe(UNAVAILABLE)
    expect(formatMetricValue('resistanceEmergenceRate', undefined)).toBe(UNAVAILABLE)
    expect(formatMetricValue('cumulativeResistanceBurden', Number.NaN)).toBe(UNAVAILABLE)
  })

  it('labels every metric the API returns', () => {
    for (const key of Object.keys(ppo.metrics)) {
      expect(METRIC_LABELS).toHaveProperty(key)
    }
  })
})

describe('comparison rows and trajectories', () => {
  it('builds the paired rows from returned metrics without altering them', () => {
    const rows = buildMetricRows(ppo.metrics, baseline.metrics)
    expect(rows.map((row) => row.key)).toEqual([...COMPARISON_METRIC_KEYS])
    const burden = rows.find((row) => row.key === 'cumulativeResistanceBurden')
    expect(burden?.ppo).toBe(ppo.metrics.cumulativeResistanceBurden)
    expect(burden?.baseline).toBe(baseline.metrics.cumulativeResistanceBurden)
  })

  it('aligns per-state counts by state index using only returned values', () => {
    const series = buildTrajectorySeries(ppo, baseline, 'resistantCount')
    expect(series).toHaveLength(9)
    expect(series[0]).toEqual({ step: 0, ppo: 1, baseline: 1 })
    expect(series[8]).toEqual({
      step: 8,
      ppo: ppo.states[8]?.resistantCount,
      baseline: baseline.states[8]?.resistantCount,
    })
  })

  it('represents a terminal start as a single state', () => {
    const terminal = fixtures.comparisonTerminal.ppo as StrategyResult
    expect(buildTrajectorySeries(terminal, terminal, 'resistantCount')).toEqual([
      { step: 0, ppo: 7, baseline: 7 },
    ])
    expect(terminal.metrics.cumulativeResistanceBurden).toBe(8)
    expect(terminal.metrics.treatmentSteps).toBe(0)
    expect(terminal.metrics.susceptibleActionRate).toBeNull()
  })
})
