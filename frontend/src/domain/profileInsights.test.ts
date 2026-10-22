import { describe, expect, it } from 'vitest'
import { buildCatalogue } from './antibiotics'
import { buildInsights } from './profileInsights'
import { fixtures } from '@/test/fixtures/api-fixtures'
import type { StrategyResult } from './types'

const entries = buildCatalogue(fixtures.antibiotics)
const ppo = fixtures.comparison.ppo as StrategyResult
const baseline = fixtures.comparison.baseline as StrategyResult

describe('buildInsights', () => {
  it('names the resistant antibiotics of the starting profile', () => {
    const resistant = ppo.initialProfile.filter((state) => state === 1).length
    const [current] = buildInsights(ppo, baseline, entries)

    expect(current?.id).toBe('current')
    expect(current?.text).toContain(`${resistant} of 7`)
  })

  it('says so when nothing is resistant, and when everything is', () => {
    const none = { ...ppo, initialProfile: ppo.initialProfile.map(() => 0 as const) }
    const all = { ...ppo, initialProfile: ppo.initialProfile.map(() => 1 as const) }

    expect(buildInsights(none, baseline, entries)[0]).toMatchObject({ tone: 'good', text: 'No antibiotic is resistant in this profile.' })
    expect(buildInsights(all, baseline, entries)[0]?.text).toContain('no treatment step is possible')
  })

  it('compares the final resistant counts of PPO and the baseline without ranking anything else', () => {
    const better = { ...ppo, metrics: { ...ppo.metrics, finalResistantCount: 1 } }
    const worse = { ...ppo, metrics: { ...ppo.metrics, finalResistantCount: 6 } }
    const even = { ...baseline, metrics: { ...baseline.metrics, finalResistantCount: 3 } }
    const same = { ...ppo, metrics: { ...ppo.metrics, finalResistantCount: 3 } }

    expect(buildInsights(better, { ...baseline, metrics: { ...baseline.metrics, finalResistantCount: 4 } }, entries)[2]).toMatchObject({ tone: 'good', text: 'PPO ends with 1 resistant, the random baseline with 4.' })
    expect(buildInsights(worse, { ...baseline, metrics: { ...baseline.metrics, finalResistantCount: 4 } }, entries)[2]?.tone).toBe('warn')
    expect(buildInsights(same, even, entries)[2]).toMatchObject({ tone: 'info', text: 'PPO and the random baseline both end with 3 resistant.' })
  })

  it('describes the change over the run when there is no baseline', () => {
    const [, , change] = buildInsights(ppo, null, entries)

    expect(change?.id).toBe('comparison')
    expect(change?.text).toContain(`from ${ppo.metrics.initialResistantCount} at the start to ${ppo.metrics.finalResistantCount} at the end`)
  })

  it('reports that no step is possible when PPO took none', () => {
    const [, first] = buildInsights({ ...ppo, steps: [] }, baseline, entries)

    expect(first).toMatchObject({ id: 'first-step', tone: 'warn', text: 'PPO takes no step: no susceptible antibiotic remains.' })
  })
})
