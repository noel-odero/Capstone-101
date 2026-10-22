import type { ResistanceProfile, StepTrace, StrategyResult } from './types'

/** The profile after each step, starting with the initial one: index n is the state reached after n actions. */
export function profilesFromSteps(initialProfile: ResistanceProfile, steps: readonly StepTrace[]): ResistanceProfile[] {
  const ordered = [...steps].sort((left, right) => left.treatmentStepAfter - right.treatmentStepAfter)
  return [initialProfile, ...ordered.map((step) => step.resistanceProfileAfter)]
}

/**
 * For each state, the profile index of the antibiotic selected to reach it (null for the initial state). An action id is the
 * antibiotic's position in the profile, which the antibiotic catalogue is checked for before it is used.
 */
export function actionsFromSteps(steps: readonly StepTrace[]): Array<number | null> {
  const ordered = [...steps].sort((left, right) => left.treatmentStepAfter - right.treatmentStepAfter)
  return [null, ...ordered.map((step) => step.actionId)]
}

export function profilesOf(result: StrategyResult): ResistanceProfile[] {
  return profilesFromSteps(result.initialProfile, result.steps)
}

export function stepAt(steps: readonly StepTrace[], treatmentStep: number): StepTrace | undefined {
  return steps.find((step) => step.treatmentStepAfter === treatmentStep)
}

/** Highest treatment step reached by any of the given step lists (the longest episode). */
export function lastStepOf(...stepLists: ReadonlyArray<readonly StepTrace[]>): number {
  return Math.max(0, ...stepLists.flatMap((steps) => steps.map((step) => step.treatmentStepAfter)))
}
