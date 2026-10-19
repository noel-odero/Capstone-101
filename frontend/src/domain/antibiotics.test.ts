import { describe, expect, it } from 'vitest'
import { CatalogueError, buildCatalogue, drugLabel, findAntibioticByName, formatDrugName } from './antibiotics'
import { fixtures } from '@/test/fixtures/api-fixtures'

describe('antibiotic catalogue', () => {
  const entries = buildCatalogue(fixtures.antibiotics)

  it('keeps the server order and ties each profile position to its action id', () => {
    expect(entries.map((entry) => entry.actionId)).toEqual([0, 1, 2, 3, 4, 5, 6])
    expect(entries.map((entry) => entry.index)).toEqual([0, 1, 2, 3, 4, 5, 6])
    expect(entries.map((entry) => entry.name)).toEqual(fixtures.model.antibioticOrder)
  })

  it('uses the server name and adds only a presentation abbreviation', () => {
    expect(entries[0]).toMatchObject({ name: 'CIPROFLOXACIN', displayName: 'Ciprofloxacin', abbreviation: 'CIP' })
    expect(entries.map((entry) => entry.abbreviation)).toEqual(['CIP', 'NIT', 'FOS', 'TMP', 'GEN', 'MEC', 'CAZ'])
  })

  it('gives an unknown antibiotic no abbreviation rather than inventing one', () => {
    const catalogue = {
      ...fixtures.antibiotics,
      antibiotics: fixtures.antibiotics.antibiotics.map((item, index) => (index === 6 ? { ...item, name: 'NEWDRUG' } : item)),
    }
    expect(buildCatalogue(catalogue)[6]?.abbreviation).toBeNull()
  })

  it('rejects a catalogue whose action ids do not match profile positions', () => {
    const swapped = {
      ...fixtures.antibiotics,
      antibiotics: [...fixtures.antibiotics.antibiotics].reverse(),
    }
    expect(() => buildCatalogue(swapped)).toThrow(CatalogueError)
  })

  it('rejects a catalogue that does not have seven antibiotics', () => {
    expect(() => buildCatalogue({ ...fixtures.antibiotics, antibiotics: fixtures.antibiotics.antibiotics.slice(0, 6) })).toThrow(
      CatalogueError,
    )
  })

  it('finds antibiotics and labels names case-insensitively, with a fallback when the catalogue is missing', () => {
    expect(findAntibioticByName(entries, 'gentamicin')?.actionId).toBe(4)
    expect(drugLabel(entries, 'GENTAMICIN')).toBe('Gentamicin')
    expect(drugLabel(undefined, 'GENTAMICIN')).toBe('Gentamicin')
    expect(formatDrugName('')).toBe('')
  })
})
