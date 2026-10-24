import { profileToCode } from '@/domain/profile'
import { fixtures, rawFixtures } from '@/test/fixtures/api-fixtures'
import { baseRoutes, mockFetch } from '@/test/mock-api'
import { renderApp } from '@/test/test-utils'
import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

const session = {
  isAuthenticated: true,
  user: { displayName: 'Ada Researcher', email: 'ada@example.org' },
  csrfToken: 'token',
}
const run = rawFixtures.recentRuns.items.find((item) => item.kind === 'comparison')
if (!run) {
  throw new Error('The captured recent runs have no comparison.')
}
const runId = run.id

function routes(
  runs: unknown = { ...rawFixtures.recentRuns, items: [run], totalCount: 1 },
  includeDqn = false,
) {
  return baseRoutes({
    'GET /api/v1/auth/session': { body: session },
    'GET /api/v1/simulations/recent': { body: runs },
    'GET /api/v1/analyses': { body: runs },
    [`GET /api/v1/comparisons/${runId}`]: {
      body: {
        ...rawFixtures.comparison,
        id: runId,
        ...(includeDqn ? { dqn: { ...rawFixtures.comparison.ppo, strategy: 'dqn' } } : {}),
      },
    },
  })
}

describe('E. coli Profile page', () => {
  it('shows the latest initial profile, its resistance level and strategy activity', async () => {
    mockFetch(routes(undefined, true))
    renderApp('/app/profile')

    const initial = fixtures.comparison.ppo?.initialProfile ?? []
    expect(
      await screen.findByRole(
        'heading',
        { name: 'Current Resistance Profile' },
        { timeout: 10000 },
      ),
    ).toBeInTheDocument()
    expect(screen.getByLabelText(`Profile ${profileToCode(initial)}`)).toBeInTheDocument()
    expect(screen.getByText('PPO + DQN')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Analyze with DQN' })).not.toBeInTheDocument()

    const drugs = within(
      screen.getByRole('list', { name: 'Resistance of each antibiotic' }),
    ).getAllByRole('listitem')
    expect(drugs).toHaveLength(7)
    initial.forEach((state, index) => {
      expect(drugs[index]).toHaveAccessibleName(
        new RegExp(state === 1 ? 'resistant$' : 'susceptible$'),
      )
    })

    const resistant = initial.filter((state) => state === 1).length
    expect(screen.getByLabelText('Resistance level')).toHaveTextContent(`${resistant} / 7`)
  })

  it('keeps results and history in the sidebar without duplicating profile tabs', async () => {
    mockFetch(routes())
    renderApp('/app/profile')

    await screen.findByRole('heading', { name: 'Current Resistance Profile' })
    expect(screen.queryByRole('navigation', { name: 'Profile sections' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Policy-selected sequence' })).not.toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Resistance Trend' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Recent Activity' })).toBeInTheDocument()
    const navigation = screen.getByRole('navigation', { name: 'Workspace' })
    expect(within(navigation).getByRole('link', { name: 'Analysis Results' })).toHaveAttribute(
      'href',
      '/app/recommendations',
    )
    expect(within(navigation).getByRole('link', { name: 'Analysis History' })).toHaveAttribute(
      'href',
      '/app/history',
    )
  })

  it('does not show the removed evolution and model-details section', async () => {
    mockFetch(routes())
    renderApp('/app/profile')

    await screen.findByRole('heading', { name: 'Current Resistance Profile' })
    expect(
      screen.queryByText('Explore resistance evolution and model details'),
    ).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Key insights' })).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Model parameters' })).not.toBeInTheDocument()
  })

  it('invites a first analysis instead of showing numbers when there are no runs', async () => {
    mockFetch(routes({ items: [], page: 1, pageSize: 10, totalCount: 0 }))
    renderApp('/app/profile')

    expect(await screen.findByText('No profile yet')).toBeInTheDocument()
    expect(
      screen.queryByRole('heading', { name: 'Current Resistance Profile' }),
    ).not.toBeInTheDocument()
  })

  it('keeps history accessible through its dedicated navigation and saved 3D analyses', async () => {
    mockFetch(routes())
    renderApp('/app/history')

    await screen.findByRole('heading', { name: 'Analysis History' })
    const navigation = screen.getByRole('navigation', { name: 'Workspace' })
    expect(within(navigation).getByRole('link', { name: 'Analysis History' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(within(navigation).getByRole('link', { name: 'E. coli Profile' })).toHaveAttribute(
      'href',
      '/app/profile',
    )
    const history = await screen.findByRole('table', { name: 'Your analyses, newest first' })
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
    expect(screen.queryByRole('form', { name: 'Filter saved analyses' })).not.toBeInTheDocument()
    expect(within(navigation).getByRole('link', { name: 'Analysis Insights' })).toHaveAttribute(
      'href',
      '/app/insights',
    )
    expect(within(history).getByRole('link', { name: 'View Analysis' })).toHaveAttribute(
      'href',
      `/app/simulation/${runId}`,
    )
  })
})
