import {
  antibioticCatalogueSchema,
  profileEvidenceSchema,
  type AntibioticCatalogue,
  type ResistanceProfile,
} from '@/domain/types'
import { requestJson, TIMEOUTS } from './http-client'

export function getAntibiotics(signal?: AbortSignal): Promise<AntibioticCatalogue> {
  return requestJson('/antibiotics', antibioticCatalogueSchema, { signal })
}

export function inspectProfile(profile: ResistanceProfile, signal?: AbortSignal) {
  return requestJson('/profiles/validate', profileEvidenceSchema, {
    method: 'POST',
    body: { resistanceProfile: profile },
    signal,
    timeoutMs: TIMEOUTS.read,
  })
}
