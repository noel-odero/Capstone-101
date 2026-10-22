import { antibioticCatalogueSchema, type AntibioticCatalogue } from '@/domain/types'
import { requestJson } from './http-client'

export function getAntibiotics(signal?: AbortSignal): Promise<AntibioticCatalogue> {
  return requestJson('/antibiotics', antibioticCatalogueSchema, { signal })
}
