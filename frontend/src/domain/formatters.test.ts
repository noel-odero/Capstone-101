import { describe, expect, it } from 'vitest'
import { SEED_MAX, parseSeedInput } from './seeds'
import { formatDateTime, formatProbability, formatSeed, formatStep, shortId, truncateHash } from './formatters'
import { GLOSSARY, STRATEGY_NAMES, outcomeLabel, terminationLabel, transitionSupportLabel } from './terminology'
import { fixtures } from '@/test/fixtures/api-fixtures'
import type { StepTrace } from './types'

describe('seed parsing', () => {
  it('treats a blank seed as "let the service generate one"', () => {
    expect(parseSeedInput('')).toEqual({ ok: true, value: undefined })
    expect(parseSeedInput('   ')).toEqual({ ok: true, value: undefined })
  })

  it('accepts whole numbers across the documented range', () => {
    expect(parseSeedInput('0')).toEqual({ ok: true, value: 0 })
    expect(parseSeedInput('4242')).toEqual({ ok: true, value: 4242 })
    expect(parseSeedInput(String(SEED_MAX))).toEqual({ ok: true, value: SEED_MAX })
  })

  it.each(['-1', '1.5', 'abc', '1e3', '4294967296', '99999999999999999999'])('rejects %s', (text) => {
    expect(parseSeedInput(text).ok).toBe(false)
  })
})

describe('formatters', () => {
  it('formats steps, ids, seeds, hashes and probabilities', () => {
    expect(formatStep(0)).toBe('Step 0 (initial state)')
    expect(formatStep(3)).toBe('Step 3')
    expect(shortId('26a324e9-6419-4c8b-a891-c8ce63f6b24e')).toBe('26a324e9')
    expect(formatSeed(4242)).toBe('4242')
    expect(formatSeed(null)).toBe('Not available')
    expect(formatProbability(0.5)).toBe('0.50')
    expect(formatProbability(null)).toBe('Not available')
    expect(truncateHash('d10c26185c9903d96d0f2003643b76be')).toBe('d10c26185c99\u202676be')
  })

  it('formats a timestamp deterministically for a given locale and zone and rejects garbage', () => {
    expect(formatDateTime('2026-10-18T14:16:06.978968+00:00', 'en-GB', 'UTC')).toContain('18 Oct 2026')
    expect(formatDateTime('not a date')).toBe('Not available')
  })
})

describe('terminology', () => {
  it('names the baseline with the public label and keeps strategy ids untouched', () => {
    expect(STRATEGY_NAMES.random_susceptible_baseline).toBe('Random Susceptible Baseline')
    expect(Object.keys(STRATEGY_NAMES)).toEqual(['ppo', 'random_susceptible_baseline'])
  })

  it('separates transition support from susceptibility in its wording', () => {
    expect(transitionSupportLabel(false)).toBe('No supported transition data')
    expect(transitionSupportLabel(true)).toBe('Transition data available')
    expect(GLOSSARY.unsupported).toMatch(/not evidence that the antibiotic worked/i)
    expect(GLOSSARY.susceptible).toMatch(/not clinical efficacy/i)
  })

  it('describes outcomes from the step, not from susceptibility', () => {
    const unsupported = fixtures.comparison.ppo?.steps[0] as StepTrace
    expect(outcomeLabel(unsupported)).toMatch(/profile unchanged/i)
    const supported = fixtures.comparison.baseline?.steps.find((step) => step.transitionStatus === 'cross_resistance') as StepTrace
    expect(outcomeLabel(supported)).toMatch(/cross-resistance/i)
  })

  it('translates termination reasons and falls back to readable text for new ones', () => {
    expect(terminationLabel('no_effective_antibiotic')).toBe('No susceptible antibiotic remained')
    expect(terminationLabel('some_new_reason')).toBe('some new reason')
  })

  it('contains none of the unsupported clinical claims', () => {
    const everything = [...Object.values(GLOSSARY), ...Object.values(STRATEGY_NAMES)].join(' ')
    expect(everything).not.toMatch(/best antibiotic|clinically effective|effective treatment|optimal policy|recommended treatment/i)
  })
})
