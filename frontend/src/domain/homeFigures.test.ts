import { describe, expect, it } from 'vitest'
import { fixtures } from '@/test/fixtures/api-fixtures'
import { countDelta, figuresFrom, formatRate, percentDelta, rateDelta } from './homeFigures'

describe('home figures', () => {
  it('reads the four numbers from the stored PPO result without estimating anything', () => {
    const ppo = fixtures.comparison.ppo
    if (!ppo) {
      throw new Error('The comparison fixture has no PPO result.')
    }

    const figures = figuresFrom(ppo)

    expect(figures.burden).toBe(ppo.metrics.cumulativeResistanceBurden)
    expect(figures.remainingSusceptible).toBe(ppo.metrics.finalSusceptibleCount)
    expect(figures.susceptibleActionRate).toBe(ppo.metrics.susceptibleActionRate)
    expect(figures.newResistant).toBe(ppo.finalProfile.filter((value, index) => value === 1 && ppo.initialProfile[index] === 0).length)
  })

  it('shows a relative change, and the absolute change when the previous value was zero', () => {
    expect(percentDelta(2.7, 4.2, false)).toEqual({ direction: 'down', text: '36%', tone: 'good' })
    expect(percentDelta(1, 0, false)).toEqual({ direction: 'up', text: '1', tone: 'bad' })
    expect(percentDelta(0, 0, false)).toEqual({ direction: 'flat', text: '0%', tone: 'neutral' })
  })

  it('marks an increase in susceptible options as good and a decrease as bad', () => {
    expect(countDelta(5, 4, true)).toEqual({ direction: 'up', text: '1', tone: 'good' })
    expect(countDelta(3, 4, true)).toEqual({ direction: 'down', text: '1', tone: 'bad' })
  })

  it('reports a rate change in percentage points and formats a missing rate as nothing', () => {
    expect(rateDelta(0.9, 0.85, true)).toEqual({ direction: 'up', text: '5 pts', tone: 'good' })
    expect(formatRate(1)).toBe('100%')
    expect(formatRate(null)).toBeNull()
  })
})
