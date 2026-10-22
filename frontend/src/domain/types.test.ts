import { fixtures, rawFixtures } from '@/test/fixtures/api-fixtures'
import { describe, expect, it } from 'vitest'
import { problemDetailsSchema, recentRunsSchema } from './types'

describe('API schemas against real captured responses', () => {
  it('accepts every captured response (a contract change fails here)', () => {
    expect(fixtures.health.ready).toBe(true)
    expect(fixtures.model.modelId).toBe('ppo_seed_12000')
    expect(fixtures.model.horizon).toBe(8)
    expect(fixtures.comparison.status).toBe('completed')
    expect(fixtures.comparison.isPersisted).toBe(true)
    expect(fixtures.simulationPpo.result?.strategy).toBe('ppo')
    expect(fixtures.simulationBaseline.result?.strategy).toBe('random_susceptible_baseline')
    expect(fixtures.recentRuns.items.map((item) => item.kind)).toContain('comparison')
  })

  it('keeps strategy identifiers exactly as the backend names them', () => {
    expect(fixtures.comparison.ppo?.strategy).toBe('ppo')
    expect(fixtures.comparison.baseline?.strategy).toBe('random_susceptible_baseline')
  })

  it('represents a terminal start as one state and no steps', () => {
    const terminal = fixtures.comparisonTerminal
    expect(terminal.ppo?.states).toHaveLength(1)
    expect(terminal.ppo?.steps).toHaveLength(0)
    expect(terminal.ppo?.terminationReason).toBe('no_effective_antibiotic')
  })

  it('numbers steps from zero, with each state following its action', () => {
    const steps = fixtures.comparison.baseline?.steps ?? []
    steps.forEach((step, index) => {
      expect(step.stepIndex).toBe(index)
      expect(step.treatmentStepAfter).toBe(index + 1)
    })
  })

  it('rejects an unknown strategy or run kind rather than guessing', () => {
    const items = rawFixtures.recentRuns.items.map((item) => ({ ...item, kind: 'mystery' }))
    expect(recentRunsSchema.safeParse({ ...rawFixtures.recentRuns, items }).success).toBe(false)
  })

  it('reads problem details with a code, correlation id and field errors', () => {
    const problem = problemDetailsSchema.parse(rawFixtures.problemValidation)
    expect(problem.code).toBe('validation_failed')
    expect(problem.correlationId).toBeTruthy()
    expect(problem.errors?.['resistanceProfile']).toHaveLength(1)
  })
})
