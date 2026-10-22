import type { ResistanceProfile, ResistanceState } from './types'

export const ANTIBIOTIC_COUNT = 7
export const SUSCEPTIBLE: ResistanceState = 0
export const RESISTANT: ResistanceState = 1

const PROFILE_CODE_PATTERN = /^[01]{7}$/

export function allSusceptibleProfile(): ResistanceProfile {
  return Array.from({ length: ANTIBIOTIC_COUNT }, () => SUSCEPTIBLE)
}

export function countResistant(profile: ResistanceProfile): number {
  return profile.filter((state) => state === RESISTANT).length
}

export function countSusceptible(profile: ResistanceProfile): number {
  return profile.length - countResistant(profile)
}

/** True when no antibiotic is susceptible, so the simulator has no feasible action and the episode is terminal. */
export function isAllResistant(profile: ResistanceProfile): boolean {
  return profile.length === ANTIBIOTIC_COUNT && countResistant(profile) === ANTIBIOTIC_COUNT
}

export function toggleAntibiotic(profile: ResistanceProfile, index: number): ResistanceProfile {
  if (index < 0 || index >= profile.length) {
    throw new RangeError(
      `Antibiotic index ${index} is outside the ${profile.length}-element profile.`,
    )
  }
  return profile.map((state, position) =>
    position === index ? (state === RESISTANT ? SUSCEPTIBLE : RESISTANT) : state,
  )
}

/**
 * Display and URL form of a profile: seven 0/1 characters in canonical antibiotic order (0 susceptible,
 * 1 resistant). The scientific contract does not define a profile identifier, so this is a presentation code only.
 */
export function profileToCode(profile: ResistanceProfile): string {
  return profile.join('')
}

/** Parses the code produced by `profileToCode`; returns null for anything that is not exactly seven 0/1 characters. */
export function parseProfileCode(code: string | null | undefined): ResistanceProfile | null {
  if (code === null || code === undefined || !PROFILE_CODE_PATTERN.test(code)) {
    return null
  }
  return Array.from(code, (character) => (character === '1' ? RESISTANT : SUSCEPTIBLE))
}
