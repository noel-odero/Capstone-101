import type { MetricDefinitions, StateSnapshot, StrategyMetrics, StrategyResult } from './types'

export type MetricKey = keyof StrategyMetrics

export const UNAVAILABLE = 'Not available'

/** Interface titles for metrics. Meanings come from the server's `metricDefinitions`, never from this file. */
export const METRIC_LABELS: Readonly<Record<MetricKey, string>> = {
  cumulativeResistanceBurden: 'Cumulative resistance burden',
  cumulativeReward: 'Cumulative reward',
  treatmentSteps: 'Treatment steps',
  initialResistantCount: 'Initial resistant antibiotics',
  finalResistantCount: 'Final resistant antibiotics',
  finalSusceptibleCount: 'Remaining susceptible options',
  changeInSusceptibleCount: 'Change in susceptible options',
  resistanceEmergenceEvents: 'Resistance-emergence events',
  resistanceEmergenceRate: 'Resistance-emergence rate',
  susceptibleActionRate: 'Susceptible-action rate',
  unsupportedStepCount: 'Steps without supported transition data',
  cumulativeAntibioticExposure: 'Antibiotic administrations',
}

/** Metrics shown side by side for the two strategies, in reading order. */
export const COMPARISON_METRIC_KEYS = [
  'cumulativeResistanceBurden',
  'finalResistantCount',
  'resistanceEmergenceEvents',
  'finalSusceptibleCount',
  'unsupportedStepCount',
] as const satisfies readonly MetricKey[]

const FRACTIONAL_KEYS: ReadonlySet<MetricKey> = new Set([
  'cumulativeResistanceBurden',
  'cumulativeReward',
  'resistanceEmergenceRate',
  'susceptibleActionRate',
])

/** Formats a metric exactly as returned (rounded for display only); a missing value is never shown as zero. */
export function formatMetricValue(key: MetricKey, value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return UNAVAILABLE
  }
  if (FRACTIONAL_KEYS.has(key)) {
    return value.toFixed(2)
  }
  if (key === 'changeInSusceptibleCount' && value > 0) {
    return `+${value}`
  }
  return value < 0 ? `\u2212${Math.abs(value)}` : String(value)
}

export function metricLabel(key: MetricKey): string {
  return METRIC_LABELS[key]
}

export function metricDefinitionFor(definitions: MetricDefinitions | undefined, key: MetricKey) {
  return definitions?.[key]
}

export interface MetricRow {
  key: MetricKey
  label: string
  ppo: number | null
  baseline: number | null
}

export function buildMetricRows(ppo: StrategyMetrics, baseline: StrategyMetrics): MetricRow[] {
  return COMPARISON_METRIC_KEYS.map((key) => ({
    key,
    label: METRIC_LABELS[key],
    ppo: ppo[key],
    baseline: baseline[key],
  }))
}

export type TrajectoryField = 'resistantCount' | 'susceptibleCount'

export interface TrajectoryPoint {
  step: number
  ppo: number | null
  baseline: number | null
}

function valueAt(result: StrategyResult, step: number, field: TrajectoryField): number | null {
  const state: StateSnapshot | undefined = result.states.find((candidate) => candidate.stateIndex === step)
  return state ? state[field] : null
}

/**
 * Per-state counts returned by the API, aligned by state index. A strategy whose episode ended earlier has no
 * point for later steps (null), which the chart leaves as a gap rather than extending the last value.
 */
export function buildTrajectorySeries(
  ppo: StrategyResult,
  baseline: StrategyResult,
  field: TrajectoryField,
): TrajectoryPoint[] {
  const lastStep = Math.max(
    ...ppo.states.map((state) => state.stateIndex),
    ...baseline.states.map((state) => state.stateIndex),
    0,
  )
  return Array.from({ length: lastStep + 1 }, (_, step) => ({
    step,
    ppo: valueAt(ppo, step, field),
    baseline: valueAt(baseline, step, field),
  }))
}

/** Highest state index present in either result (the longest episode). */
export function lastStateIndex(...results: readonly StrategyResult[]): number {
  return Math.max(0, ...results.flatMap((result) => result.states.map((state) => state.stateIndex)))
}
