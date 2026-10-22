import { describe, expect, it } from 'vitest'
import {
  allResistantProfile,
  allSusceptibleProfile,
  countResistant,
  countSusceptible,
  isAllResistant,
  isResistanceProfile,
  parseProfileCode,
  profileToCode,
  profilesEqual,
  toggleAntibiotic,
} from './profile'

describe('profile helpers', () => {
  it('builds the all-susceptible and all-resistant profiles with seven entries', () => {
    expect(allSusceptibleProfile()).toEqual([0, 0, 0, 0, 0, 0, 0])
    expect(allResistantProfile()).toEqual([1, 1, 1, 1, 1, 1, 1])
  })

  it('counts resistant and susceptible antibiotics', () => {
    const profile = parseProfileCode('0100110')
    expect(profile).not.toBeNull()
    expect(countResistant(profile ?? [])).toBe(3)
    expect(countSusceptible(profile ?? [])).toBe(4)
  })

  it('treats only a profile with every antibiotic resistant as terminal', () => {
    expect(isAllResistant(allResistantProfile())).toBe(true)
    expect(isAllResistant(parseProfileCode('1111110') ?? [])).toBe(false)
    expect(isAllResistant(allSusceptibleProfile())).toBe(false)
  })

  it('round-trips every one of the 128 profiles through its code', () => {
    for (let value = 0; value < 128; value += 1) {
      const code = value.toString(2).padStart(7, '0')
      const profile = parseProfileCode(code)
      expect(profile).not.toBeNull()
      expect(profileToCode(profile ?? [])).toBe(code)
    }
  })

  it.each([null, undefined, '', '010000', '01000000', '0100002', 'abcdefg', '0 10000'])(
    'rejects the invalid profile code %s',
    (code) => {
      expect(parseProfileCode(code)).toBeNull()
    },
  )

  it('validates the shape of a profile', () => {
    expect(isResistanceProfile([0, 1, 0, 1, 0, 1, 0])).toBe(true)
    expect(isResistanceProfile([0, 1, 0])).toBe(false)
    expect(isResistanceProfile([0, 1, 0, 1, 0, 1, 2])).toBe(false)
    expect(isResistanceProfile('0101010')).toBe(false)
  })

  it('toggles one antibiotic without mutating the original', () => {
    const original = allSusceptibleProfile()
    const toggled = toggleAntibiotic(original, 3)
    expect(toggled).toEqual([0, 0, 0, 1, 0, 0, 0])
    expect(original).toEqual([0, 0, 0, 0, 0, 0, 0])
    expect(toggleAntibiotic(toggled, 3)).toEqual(original)
  })

  it('refuses to toggle a position outside the profile', () => {
    expect(() => toggleAntibiotic(allSusceptibleProfile(), 7)).toThrow(RangeError)
    expect(() => toggleAntibiotic(allSusceptibleProfile(), -1)).toThrow(RangeError)
  })

  it('compares profiles by value', () => {
    expect(profilesEqual(allSusceptibleProfile(), allSusceptibleProfile())).toBe(true)
    expect(profilesEqual(allSusceptibleProfile(), allResistantProfile())).toBe(false)
  })
})
