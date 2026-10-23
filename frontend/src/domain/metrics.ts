import type { StrategyMetrics, StrategyResult } from './types'

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

/** Metrics shown side by side, in reading order. */
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

export interface MetricRow {
  key: MetricKey
  label: string
  values: (number | null)[]
}

export function buildMetricRows(results: readonly StrategyResult[]): MetricRow[] {
  return COMPARISON_METRIC_KEYS.map((key) => ({
    key,
    label: METRIC_LABELS[key],
    values: results.map((result) => result.metrics[key]),
  }))
}

export type TrajectoryField = 'resistantCount' | 'susceptibleCount'

export function comparePolicyTraces(left: StrategyResult, right: StrategyResult) {
  const sameChoices =
    left.steps.length === right.steps.length &&
    left.steps.every(
      (step, index) =>
        step.actionId === right.steps[index]?.actionId &&
        step.treatmentStepAfter === right.steps[index]?.treatmentStepAfter,
    )
  const sameCounts =
    left.states.length === right.states.length &&
    left.states.every(
      (state, index) =>
        state.stateIndex === right.states[index]?.stateIndex &&
        state.resistantCount === right.states[index]?.resistantCount,
    )
  const sameProfiles =
    left.states.length === right.states.length &&
    left.states.every(
      (state, index) =>
        state.stateIndex === right.states[index]?.stateIndex &&
        state.resistanceProfile.every(
          (bit, drug) => bit === right.states[index]?.resistanceProfile[drug],
        ),
    )
  return { sameChoices, sameCounts, sameProfiles }
}

export interface TrajectoryPoint {
  step: number
  [strategy: string]: number | null
}

/**
 * Per-state counts returned by the API, aligned by state index. A strategy whose episode ended earlier has no
 * point for later steps (null), which the chart leaves as a gap rather than extending the last value.
 */
export function buildTrajectorySeries(
  results: readonly StrategyResult[],
  field: TrajectoryField,
): TrajectoryPoint[] {
  const lastStep = Math.max(
    ...results.flatMap((result) => result.states.map((state) => state.stateIndex)),
    0,
  )
  return Array.from({ length: lastStep + 1 }, (_, step) => ({
    step,
    ...Object.fromEntries(
      results.map((result) => [
        result.strategy,
        result.states.find((state) => state.stateIndex === step)?.[field] ?? null,
      ]),
    ),
  }))
}
