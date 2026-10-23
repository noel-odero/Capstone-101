import type { StepTrace } from './types'

/** Highest treatment step reached by any of the given step lists (the longest episode). */
export function lastStepOf(...stepLists: ReadonlyArray<readonly StepTrace[]>): number {
  return Math.max(0, ...stepLists.flatMap((steps) => steps.map((step) => step.treatmentStepAfter)))
}
