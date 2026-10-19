import {
  antibioticCatalogueSchema,
  profileValidationSchema,
  type AntibioticCatalogue,
  type ProfileValidation,
  type ResistanceProfile,
} from '@/domain/types'
import { requestJson } from './http-client'

export function getAntibiotics(signal?: AbortSignal): Promise<AntibioticCatalogue> {
  return requestJson('/antibiotics', antibioticCatalogueSchema, { signal })
}

/** Read-only check: nothing is stored, so this POST is safe to repeat. */
export function validateProfile(
  resistanceProfile: ResistanceProfile,
  signal?: AbortSignal,
): Promise<ProfileValidation> {
  return requestJson('/profiles/validate', profileValidationSchema, {
    method: 'POST',
    body: { resistanceProfile },
    signal,
  })
}
