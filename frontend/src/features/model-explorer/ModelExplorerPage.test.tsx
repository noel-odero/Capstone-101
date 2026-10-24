import { screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { rawFixtures } from '@/test/fixtures/api-fixtures'
import { baseRoutes, mockFetch, type RecordedCall } from '@/test/mock-api'
import { renderApp } from '@/test/test-utils'
import { MODEL_STATES } from './model-states'

const session = {
  isAuthenticated: true,
  user: { displayName: 'Researcher', email: 'research@example.org' },
  csrfToken: 'token',
}

// Deliberately state-dependent test evidence, not a copy of the production interaction matrix.
function evidenceResponse(call: RecordedCall) {
  const profile = (call.body as { resistanceProfile: number[] }).resistanceProfile
  const feasibleActions = rawFixtures.antibiotics.antibiotics
    .filter((entry) => profile[entry.actionId] === 0)
    .map((entry) => ({
      ...entry,
      antibiotic: entry.name,
      hasCandidateTransition: entry.actionId === 0 && profile[1] === 0,
    }))
  return {
    body: {
      resistanceProfile: profile,
      resistantCount: profile.filter(Boolean).length,
      susceptibleOptionCount: feasibleActions.length,
      feasibleActions,
      isTerminal: feasibleActions.length === 0,
      horizon: 8,
      scenarioId: 'REF_UNIFORM_SUPPORTED',
      interactionDataSha256: rawFixtures.model.interactionDataSha256,
      transitionEvidence: rawFixtures.antibiotics.antibiotics.map((entry) => ({
        actionId: entry.actionId,
        antibiotic: entry.name,
        eligible: profile[entry.actionId] === 0,
        candidates:
          entry.actionId === 0 && profile[0] === 0 && profile[1] === 0
            ? [
                {
                  targetDrug: 'NITROFURANTOIN',
                  outcome: 'cross_resistance',
                  sourceIds: ['TEST_SOURCE'],
                },
              ]
            : [],
      })),
    },
  }
}

function serving(extra = {}) {
  return mockFetch(
    baseRoutes({
      'GET /api/v1/auth/session': { body: session },
      'POST /api/v1/profiles/validate': evidenceResponse,
      ...extra,
    }),
  )
}

describe('E. coli Model Explorer', () => {
  it('enumerates the complete binary state space and filters the 35 three-resistant states without editing a sample', async () => {
    const api = serving()
    const user = userEvent.setup()
    renderApp('/app/profile')
    await screen.findByRole('heading', { name: 'E. coli Model Explorer' })
    expect(screen.getAllByRole('button', { name: /^State [01]{7},/ })).toHaveLength(128)
    expect(new Set(MODEL_STATES.map((state) => state.code)).size).toBe(128)
    expect(screen.queryByRole('switch')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '3 resistant: 35 states' }))
    expect(screen.getAllByRole('button', { name: /^State [01]{7},/ })).toHaveLength(35)
    expect(screen.getByRole('link', { name: 'Evaluate this state' })).toHaveAttribute(
      'href',
      '/app/simulation/new?profile=0000111',
    )
    expect(api.callsTo('POST /api/v1/samples')).toHaveLength(0)
    expect(api.callsTo('POST /api/v1/comparisons')).toHaveLength(0)
  })

  it('distinguishes ineligible actions from eligible data gaps and exposes actual candidate links and source IDs', async () => {
    serving()
    const user = userEvent.setup()
    const { router } = renderApp('/app/profile')
    await user.click(
      await screen.findByRole('button', { name: 'Inspect Ciprofloxacin candidates' }),
    )
    expect(screen.getByText('Sources: TEST_SOURCE')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Explore candidate state 0100000' }))
    await waitFor(() => expect(router.state.location.search).toContain('state=0100000'))
    const actions = await screen.findByRole('list', {
      name: 'Action eligibility and transition coverage',
    })
    await waitFor(() =>
      expect(within(actions).getByText('Nitrofurantoin').closest('li')).toHaveTextContent(
        'Not eligible',
      ),
    )
    expect(within(actions).getByText('Ciprofloxacin').closest('li')).toHaveTextContent(
      'No candidate data',
    )
    expect(within(actions).getByText('Fosfomycin').closest('li')).toHaveTextContent(
      'No candidate data',
    )
    expect(screen.queryByText('Sources: TEST_SOURCE')).not.toBeInTheDocument()
  })

  it('works without saved research and reports the all-resistant state as terminal, not seven data gaps', async () => {
    serving()
    renderApp('/app/profile?state=1111111')
    expect(
      await screen.findByText(/No action is eligible from this terminal state/),
    ).toBeInTheDocument()
    const actions = screen.getByRole('list', { name: 'Action eligibility and transition coverage' })
    expect(within(actions).getAllByText('Not eligible')).toHaveLength(7)
    expect(within(actions).queryByText('No candidate data')).not.toBeInTheDocument()
    expect(screen.getByText('No samples recorded with this state.')).toBeInTheDocument()
    expect(screen.getByText('No saved analyses started from this state.')).toBeInTheDocument()
  })

  it('queries related analyses by the selected state and uses the server total rather than counting one page', async () => {
    const sampleId = '5a1f3a7e-3c1c-4f43-9f0e-2f4d7a9b6c11'
    const run = rawFixtures.recentRuns.items.find((item) => item.kind === 'comparison')
    if (!run) throw new Error('The captured fixture must contain a comparison')
    const api = serving({
      'GET /api/v1/analyses': {
        body: {
          items: [{ ...run, initialProfile: [0, 1, 1, 1, 0, 1, 0] }],
          page: 1,
          pageSize: 10,
          totalCount: 23,
        },
      },
      'GET /api/v1/samples': {
        body: [
          {
            id: sampleId,
            label: 'UTI-1',
            addedAtUtc: '2026-10-24T10:00:00Z',
            resistanceProfile: [0, 1, 1, 1, 0, 1, 0],
            runs: [],
          },
        ],
      },
    })
    renderApp('/app/profile?state=0111010')
    expect(await screen.findByRole('link', { name: 'UTI-1' })).toHaveAttribute(
      'href',
      `/app/simulation/new?sample=${sampleId}`,
    )
    expect(screen.getByRole('heading', { name: 'Saved analyses 23' })).toBeInTheDocument()
    expect(
      api
        .callsTo('GET /api/v1/analyses')
        .some((call) => new URLSearchParams(call.search).get('profile') === '0111010'),
    ).toBe(true)
    expect(screen.getByRole('link', { name: 'Model Explorer' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(screen.getByRole('link', { name: 'Evaluate this state' })).toHaveAttribute(
      'href',
      '/app/simulation/new?profile=0111010',
    )
  })

  it('keeps the state explorer usable when evidence is unavailable instead of inventing support statuses', async () => {
    serving({
      'POST /api/v1/profiles/validate': {
        status: 503,
        body: { status: 503, title: 'Service unavailable' },
      },
    })
    renderApp('/app/profile')
    expect(await screen.findByText('Transition evidence could not be checked')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /^State [01]{7},/ })).toHaveLength(128)
    expect(
      screen.queryByRole('list', { name: 'Action eligibility and transition coverage' }),
    ).not.toBeInTheDocument()
  })
})
