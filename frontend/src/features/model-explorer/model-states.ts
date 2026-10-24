import type { AntibioticEntry } from '@/domain/antibiotics'
import { countResistant } from '@/domain/profile'
import type { ResistanceProfile, TransitionEvidenceCandidate } from '@/domain/types'

export const MODEL_STATES = Array.from({ length: 128 }, (_, index) => {
  const code = index.toString(2).padStart(7, '0')
  const profile: ResistanceProfile = Array.from(code, (bit) => (bit === '1' ? 1 : 0))
  return { code, profile, count: countResistant(profile) }
})

export function candidateProfile(
  profile: ResistanceProfile,
  entries: readonly AntibioticEntry[],
  candidate: TransitionEvidenceCandidate,
): string | null {
  const target = entries.find(
    (entry) => entry.name.toUpperCase() === candidate.targetDrug.toUpperCase(),
  )
  if (!target) return null
  const next = [...profile]
  if (candidate.outcome === 'cross_resistance') next[target.index] = 1
  if (candidate.outcome === 'collateral_sensitivity') next[target.index] = 0
  return next.join('')
}
