import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { fixtures, rawFixtures } from '@/test/fixtures/api-fixtures'
import { baseRoutes, mockFetch } from '@/test/mock-api'
import { renderApp } from '@/test/test-utils'
import { evaluationFrame, initialPlayback, playbackReducer } from './evaluation-playback'

const id = '8f34a4ef-8177-4380-92d9-3be0507efac3'
const session = {
  isAuthenticated: true,
  user: { displayName: 'Researcher', email: 'research@example.org' },
  csrfToken: 'token',
}
const ppo = fixtures.comparison.ppo
const baseline = fixtures.comparison.baseline
if (!ppo || !baseline) throw new Error('Expected recorded policy traces')
const run = {
  ...rawFixtures.comparison,
  id,
  dqn: { ...rawFixtures.comparison.ppo, strategy: 'dqn', displayLabel: 'DQN' },
}

function serving() {
  return mockFetch(
    baseRoutes({
      'GET /api/v1/auth/session': { body: session },
      [`GET /api/v1/comparisons/${id}`]: { body: run },
    }),
  )
}

describe('recorded evaluation playback', () => {
  it('separates action selection from the recorded outcome and unlocks metrics only at completion', () => {
    let state = initialPlayback(2)
    expect(state.completed).toBe(false)
    state = playbackReducer(state, { type: 'play' })
    state = playbackReducer(state, { type: 'advance' })
    expect([state.step, state.phase, state.playing, state.completed]).toEqual([
      1,
      'action',
      true,
      false,
    ])
    state = playbackReducer(state, { type: 'advance' })
    expect([state.step, state.phase, state.completed]).toEqual([1, 'outcome', false])
    state = playbackReducer(state, { type: 'advance' })
    expect([state.step, state.phase, state.completed]).toEqual([2, 'action', false])
    state = playbackReducer(state, { type: 'advance' })
    expect([state.phase, state.completed, state.playing]).toEqual(['outcome', true, false])
    state = playbackReducer(state, { type: 'play' })
    expect([state.step, state.phase, state.playing, state.completed]).toEqual([
      0,
      'initial',
      true,
      false,
    ])
  })

  it('uses stored profiles before and after the action without inventing extra states after a policy ends', () => {
    const trace = baseline.steps.find((step) => step.transitionStatus === 'cross_resistance')
    if (!trace) throw new Error('Expected recorded XR effect')
    const before = evaluationFrame(baseline, trace.treatmentStepAfter, 'action')
    const after = evaluationFrame(baseline, trace.treatmentStepAfter, 'outcome')
    expect(before.profile).toEqual(trace.resistanceProfileBefore)
    expect(before.applied).toBe(false)
    expect(after.profile).toEqual(trace.resistanceProfileAfter)
    expect(after.applied).toBe(true)
    const short = {
      ...baseline,
      steps: baseline.steps.slice(0, 2),
      states: baseline.states.slice(0, 3),
    }
    const ended = evaluationFrame(short, 8, 'outcome')
    expect(ended.profile).toEqual(short.states.at(-1)?.resistanceProfile)
    expect(ended.trace).toBeUndefined()
    expect(ended.ended).toBe(true)
    expect(ended.actualStep).toBe(2)
  })

  it('handles zero-action episodes without an animation or artificial waiting period', () => {
    const terminal = initialPlayback(0, true)
    expect(terminal.completed).toBe(true)
    expect(terminal.playing).toBe(false)
    expect(playbackReducer(terminal, { type: 'play' }).playing).toBe(false)
    expect(playbackReducer(initialPlayback(8), { type: 'seek', step: 100 }).step).toBe(8)
  })

  it('holds the pre-transition cell state until the recorded outcome and avoids duplicate antibiotic details', async () => {
    const api = serving()
    const user = userEvent.setup()
    renderApp(`/app/simulation/${id}?policy=random_susceptible_baseline`)
    await screen.findByRole('heading', { name: 'Bacterial evolution' })
    expect(
      screen.queryByRole('table', { name: 'Strategy evaluation metrics' }),
    ).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Next step' }))
    expect(screen.getByLabelText('Recorded resistance state')).toHaveAttribute(
      'data-profile',
      baseline.initialProfile.join(''),
    )
    expect(screen.queryByRole('heading', { name: 'Trimethoprim' })).not.toBeInTheDocument()
    expect(screen.queryByText('Decision trace')).not.toBeInTheDocument()
    expect(
      screen.queryByRole('group', { name: 'Inspect antibiotic states' }),
    ).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Show recorded outcome' }))
    expect(screen.getByLabelText('Recorded resistance state')).toHaveAttribute(
      'data-profile',
      baseline.steps[0]?.resistanceProfileAfter.join('') ?? '',
    )
    expect(api.callsTo('POST /api/v1/comparisons')).toHaveLength(0)
  })

  it('shows recorded resistance evolution and holds data gaps unchanged when switching policies at the same step', async () => {
    serving()
    const user = userEvent.setup()
    renderApp(`/app/simulation/${id}?policy=random_susceptible_baseline`)
    await screen.findByRole('heading', { name: 'Bacterial evolution' })
    await user.click(screen.getByRole('button', { name: 'Inspect step 5' }))
    expect(screen.getByText('Resistance gained')).toBeInTheDocument()
    const frame = evaluationFrame(baseline, 5, 'outcome')
    expect(screen.getByLabelText('Recorded resistance state')).toHaveAttribute(
      'data-profile',
      frame.profile.join(''),
    )
    const policySelector = screen.getByRole('group', { name: 'Policy shown in 3D' })
    await user.click(within(policySelector).getByRole('button', { name: 'DQN' }))
    expect(screen.getByRole('button', { name: 'Inspect step 5' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByLabelText('Recorded resistance state')).toHaveAttribute(
      'data-profile',
      ppo.initialProfile.join(''),
    )
    expect(screen.getByText('Transition data unavailable · state held')).toBeInTheDocument()
    expect(
      screen.queryByRole('table', { name: 'Strategy evaluation metrics' }),
    ).not.toBeInTheDocument()
  })

  it('reveals all recorded strategy metrics at completion and permits replay without rerunning the backend', async () => {
    const api = serving()
    const user = userEvent.setup()
    renderApp(`/app/simulation/${id}`)
    await user.click(await screen.findByRole('button', { name: 'Skip to results' }))
    const table = screen.getByRole('table', { name: 'Strategy evaluation metrics' })
    expect(within(table).getByRole('columnheader', { name: 'PPO' })).toBeInTheDocument()
    expect(within(table).getByRole('columnheader', { name: 'DQN' })).toBeInTheDocument()
    expect(within(table).getByRole('columnheader', { name: 'Random baseline' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Replay' }))
    expect(
      screen.queryByRole('table', { name: 'Strategy evaluation metrics' }),
    ).not.toBeInTheDocument()
    expect(api.callsTo('POST /api/v1/comparisons')).toHaveLength(0)
    expect(api.callsTo('POST /api/v1/simulations')).toHaveLength(0)
  })
})
