import type { Antibiotic, AntibioticCatalogue } from './types'
import { ANTIBIOTIC_COUNT } from './profile'

/**
 * One antibiotic as the interface uses it. `index` is the position in a resistance profile and equals `actionId`
 * (verified when the catalogue is built); `name` is the server's identifier; `abbreviation` is presentation only.
 */
export interface AntibioticEntry {
  index: number
  actionId: number
  name: string
  displayName: string
  abbreviation: string | null
  drugClass: string | null
}

export class CatalogueError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'CatalogueError'
  }
}

/** Conventional short labels for display only. The API supplies no codes; an unknown name simply has none. */
const ABBREVIATIONS: Readonly<Record<string, string>> = {
  CIPROFLOXACIN: 'CIP',
  NITROFURANTOIN: 'NIT',
  FOSFOMYCIN: 'FOS',
  TRIMETHOPRIM: 'TMP',
  GENTAMICIN: 'GEN',
  MECILLINAM: 'MEC',
  CEFTAZIDIME: 'CAZ',
}

export function formatDrugName(name: string): string {
  return name.length === 0 ? name : name.charAt(0).toUpperCase() + name.slice(1).toLowerCase()
}

/**
 * Builds the antibiotic list in profile order. The server lists antibiotics in canonical action order, so the
 * catalogue is rejected unless it has seven entries whose action ids are 0 to 6 in sequence; a profile position
 * and an action id are never assumed to match without that check.
 */
export function buildCatalogue(catalogue: AntibioticCatalogue): AntibioticEntry[] {
  const { antibiotics } = catalogue
  if (antibiotics.length !== ANTIBIOTIC_COUNT) {
    throw new CatalogueError(`Expected ${ANTIBIOTIC_COUNT} antibiotics but the API returned ${antibiotics.length}.`)
  }
  return antibiotics.map((antibiotic: Antibiotic, index) => {
    if (antibiotic.actionId !== index) {
      throw new CatalogueError(
        `Antibiotic ${antibiotic.name} has action id ${antibiotic.actionId} at profile position ${index}.`,
      )
    }
    return {
      index,
      actionId: antibiotic.actionId,
      name: antibiotic.name,
      displayName: formatDrugName(antibiotic.name),
      abbreviation: ABBREVIATIONS[antibiotic.name.toUpperCase()] ?? null,
      drugClass: antibiotic.drugClass,
    }
  })
}

export function findAntibioticByName(
  entries: readonly AntibioticEntry[],
  name: string,
): AntibioticEntry | undefined {
  return entries.find((entry) => entry.name.toUpperCase() === name.toUpperCase())
}

/** Readable name for any server drug string, falling back to a capitalised form when the catalogue is unavailable. */
export function drugLabel(entries: readonly AntibioticEntry[] | undefined, name: string): string {
  return (entries && findAntibioticByName(entries, name)?.displayName) ?? formatDrugName(name)
}
