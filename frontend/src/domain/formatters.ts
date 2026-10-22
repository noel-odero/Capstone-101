import { countResistant, countSusceptible } from './profile'
import type { ModelInfo, ResistanceProfile, RunStatus } from './types'
import { UNAVAILABLE } from './metrics'

const SHORT_ID_LENGTH = 8

export function shortId(id: string): string {
  return id.slice(0, SHORT_ID_LENGTH)
}

export function formatDateTime(iso: string, locale?: string, timeZone?: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) {
    return UNAVAILABLE
  }
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short', timeZone }).format(date)
}

export function formatStep(step: number): string {
  return step === 0 ? 'Step 0 (initial state)' : `Step ${step}`
}

export function formatProfileSummary(profile: ResistanceProfile): string {
  return `${countResistant(profile)} resistant, ${countSusceptible(profile)} susceptible`
}

export function formatRunStatus(status: RunStatus): string {
  return status === 'completed' ? 'Completed' : 'Failed'
}

export function formatModelId(model: Pick<ModelInfo, 'modelId'> | undefined): string {
  return model?.modelId ?? UNAVAILABLE
}

export function formatSeed(seed: number | null | undefined): string {
  return seed === null || seed === undefined ? UNAVAILABLE : String(seed)
}

export function formatProbability(value: number | null | undefined): string {
  return value === null || value === undefined ? UNAVAILABLE : value.toFixed(2)
}

export function truncateHash(hash: string): string {
  return hash.length > 16 ? `${hash.slice(0, 12)}\u2026${hash.slice(-4)}` : hash
}
