import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { profileToCode } from '@/domain/profile'
import { baseRoutes, mockFetch } from '@/test/mock-api'
import { fixtures, rawFixtures } from '@/test/fixtures/api-fixtures'
import { renderApp } from '@/test/test-utils'

const session = { isAuthenticated: true, user: { displayName: 'Ada Researcher', email: 'ada@example.org' }, csrfToken: 'token' }
const run = rawFixtures.recentRuns.items.find((item) => item.kind === 'comparison')
if (!run) {
  throw new Error('The captured recent runs have no comparison.')
}
const runId = run.id

function routes(runs: unknown = { ...rawFixtures.recentRuns, items: [run], totalCount: 1 }) {
  return baseRoutes({
    'GET /api/v1/auth/session': { body: session },
    'GET /api/v1/simulations/recent': { body: runs },
    [`GET /api/v1/comparisons/${runId}`]: { body: { ...rawFixtures.comparison, id: runId } },
  })
}

describe('E. coli Profile page', () => {
  it('shows the starting profile of the latest run, its resistance level, and the PPO sequence', async () => {
    mockFetch(routes())
    renderApp('/app/profile')

    const initial = fixtures.comparison.ppo?.initialProfile ?? []
    expect(await screen.findByRole('heading', { name: 'Resistance Profile' })).toBeInTheDocument()
    expect(screen.getByLabelText(`Profile ${profileToCode(initial)}`)).toBeInTheDocument()

    const drugs = within(screen.getByRole('list', { name: 'Resistance of each antibiotic' })).getAllByRole('listitem')
    expect(drugs).toHaveLength(7)
    initial.forEach((state, index) => {
      expect(drugs[index]).toHaveAccessibleName(new RegExp(state === 1 ? 'resistant$' : 'susceptible$'))
    })

    const resistant = initial.filter((state) => state === 1).length
    expect(screen.getByLabelText('Resistance level')).toHaveTextContent(`${resistant} / 7`)
    expect(screen.getByRole('list', { name: 'PPO-selected antibiotics in order' }).children.length).toBe(fixtures.comparison.ppo?.steps.length)
  })

  it('links to the recommendations of this run and to the treatment history', async () => {
    mockFetch(routes())
    renderApp('/app/profile')

    const tabs = await screen.findByRole('navigation', { name: 'Profile sections' })
    expect(within(tabs).getByRole('link', { name: 'Resistance evolution' })).toHaveAttribute('aria-current', 'page')
    expect(within(tabs).getByRole('link', { name: 'Treatment recommendations' })).toHaveAttribute('href', `/app/recommendations/comparison/${runId}`)
    expect(within(tabs).getByRole('link', { name: 'Treatment history' })).toHaveAttribute('href', '/app/history')
  })

  it('reads the key insights and the model parameters from the run, and starts a new simulation from this profile', async () => {
    mockFetch(routes())
    renderApp('/app/profile')

    const insights = await screen.findByRole('region', { name: 'Key insights' })
    expect(within(insights).getAllByRole('heading', { level: 3 })).toHaveLength(3)
    const parameters = screen.getByRole('region', { name: 'Model parameters' })
    expect(parameters).toHaveTextContent(rawFixtures.comparison.provenance.algorithm)
    expect(parameters).toHaveTextContent(`${rawFixtures.comparison.provenance.horizon} steps`)
    const initial = fixtures.comparison.ppo?.initialProfile ?? []
    expect(screen.getByRole('link', { name: 'Run New Simulation' })).toHaveAttribute('href', `/app/simulation/new?profile=${profileToCode(initial)}`)
  })

  it('invites a first simulation instead of showing numbers when there are no runs, and disables the recommendations tab', async () => {
    mockFetch(routes({ items: [], page: 1, pageSize: 10, totalCount: 0 }))
    renderApp('/app/profile')

    expect(await screen.findByText('No profile yet')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Resistance Profile' })).not.toBeInTheDocument()
  })

  it('keeps the same tabs on the history page, with the history tab current', async () => {
    mockFetch(routes())
    renderApp('/app/history')

    const tabs = await screen.findByRole('navigation', { name: 'Profile sections' })
    expect(within(tabs).getByRole('link', { name: 'Treatment history' })).toHaveAttribute('aria-current', 'page')
    expect(within(tabs).getByRole('link', { name: 'Resistance evolution' })).toHaveAttribute('href', '/app/profile')
  })
})
