import type { StrategyResult } from './types'

/** The four headline numbers of one run's PPO result, derived only from what the API returned. */
export interface RunFigures {
  burden: number
  /** Antibiotics susceptible at the start that are resistant at the end. */
  newResistant: number
  /** Share of treatment steps that used a susceptible antibiotic, 0 to 1; null when no steps were taken. */
  susceptibleActionRate: number | null
  remainingSusceptible: number
}

export function figuresFrom(result: StrategyResult): RunFigures {
  const newResistant = result.finalProfile.filter((value, index) => value === 1 && result.initialProfile[index] === 0).length
  return {
    burden: result.metrics.cumulativeResistanceBurden,
    newResistant,
    susceptibleActionRate: result.metrics.susceptibleActionRate,
    remainingSusceptible: result.metrics.finalSusceptibleCount,
  }
}

export type DeltaTone = 'good' | 'bad' | 'neutral'

export interface Delta {
  direction: 'up' | 'down' | 'flat'
  text: string
  tone: DeltaTone
}

const FLAT_EPSILON = 1e-9

function direction(change: number): Delta['direction'] {
  return Math.abs(change) < FLAT_EPSILON ? 'flat' : change > 0 ? 'up' : 'down'
}

function toneFor(change: number, higherIsBetter: boolean): DeltaTone {
  if (Math.abs(change) < FLAT_EPSILON) {
    return 'neutral'
  }
  return change > 0 === higherIsBetter ? 'good' : 'bad'
}

/** Relative change, as "36%". From a previous value of zero a percentage is undefined, so the absolute change is shown. */
export function percentDelta(current: number, previous: number, higherIsBetter: boolean): Delta {
  const change = current - previous
  const text =
    previous === 0
      ? Math.abs(change) < FLAT_EPSILON
        ? '0%'
        : String(Math.abs(Number(change.toFixed(2))))
      : `${Math.round((Math.abs(change) / Math.abs(previous)) * 100)}%`
  return { direction: direction(change), text, tone: toneFor(change, higherIsBetter) }
}

export function countDelta(current: number, previous: number, higherIsBetter: boolean): Delta {
  const change = current - previous
  return { direction: direction(change), text: String(Math.abs(change)), tone: toneFor(change, higherIsBetter) }
}

/** Change of a 0 to 1 rate in percentage points, as "5 pts". */
export function rateDelta(current: number, previous: number, higherIsBetter: boolean): Delta {
  const change = (current - previous) * 100
  return { direction: direction(change), text: `${Math.abs(Math.round(change))} pts`, tone: toneFor(change, higherIsBetter) }
}

export function formatRate(rate: number | null): string | null {
  return rate === null ? null : `${Math.round(rate * 100)}%`
}
