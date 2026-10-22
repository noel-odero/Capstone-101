import type { ResistanceProfile, StepTrace } from './types'

/** The profile after each step, starting with the initial one: index n is the state reached after n actions. */
export function profilesFromSteps(
  initialProfile: ResistanceProfile,
  steps: readonly StepTrace[],
): ResistanceProfile[] {
  const ordered = [...steps].sort(
    (left, right) => left.treatmentStepAfter - right.treatmentStepAfter,
  )
  return [initialProfile, ...ordered.map((step) => step.resistanceProfileAfter)]
}

/** Highest treatment step reached by any of the given step lists (the longest episode). */
export function lastStepOf(...stepLists: ReadonlyArray<readonly StepTrace[]>): number {
  return Math.max(0, ...stepLists.flatMap((steps) => steps.map((step) => step.treatmentStepAfter)))
}
