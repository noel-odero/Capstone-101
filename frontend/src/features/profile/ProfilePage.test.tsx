import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { profileToCode } from '@/domain/profile'
import { baseRoutes, mockFetch } from '@/test/mock-api'
import { fixtures, rawFixtures } from '@/test/fixtures/api-fixtures'
import { renderApp } from '@/test/test-utils'

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
    expect(
      await screen.findByRole(
        'heading',
        { name: 'Current Resistance Profile' },
        { timeout: 10000 },
      ),
    ).toBeInTheDocument()
    expect(screen.getByLabelText(`Profile ${profileToCode(initial)}`)).toBeInTheDocument()

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

  it('links to the recommendations of this run and to the treatment history', async () => {
    mockFetch(routes())
    renderApp('/app/profile')

    const tabs = await screen.findByRole('navigation', { name: 'Profile sections' })
    expect(within(tabs).getByRole('link', { name: 'Resistance evolution' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(within(tabs).getByRole('link', { name: 'Policy-selected sequence' })).toHaveAttribute(
      'href',
      `/app/recommendations/comparison/${runId}`,
    )
    expect(within(tabs).getByRole('link', { name: 'Experiment History' })).toHaveAttribute(
      'href',
      '/app/history',
    )
  })

  it('does not show the removed evolution and model-details section', async () => {
    mockFetch(routes())
    renderApp('/app/profile')

    await screen.findByRole('heading', { name: 'Current Resistance Profile' })
    expect(screen.queryByText('Explore resistance evolution and model details')).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Key insights' })).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Model parameters' })).not.toBeInTheDocument()
  })

  it('invites a first simulation instead of showing numbers when there are no runs, and disables the recommendations tab', async () => {
    mockFetch(routes({ items: [], page: 1, pageSize: 10, totalCount: 0 }))
    renderApp('/app/profile')

    expect(await screen.findByText('No profile yet')).toBeInTheDocument()
    expect(
      screen.queryByRole('heading', { name: 'Current Resistance Profile' }),
    ).not.toBeInTheDocument()
  })

  it('keeps the same tabs on the history page, with the history tab current', async () => {
    mockFetch(routes())
    renderApp('/app/history')

    const tabs = await screen.findByRole('navigation', { name: 'Profile sections' })
    expect(within(tabs).getByRole('link', { name: 'Experiment History' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(within(tabs).getByRole('link', { name: 'Resistance evolution' })).toHaveAttribute(
      'href',
      '/app/profile',
    )
  })
})
