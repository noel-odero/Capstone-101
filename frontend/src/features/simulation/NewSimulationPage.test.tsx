import { rawFixtures } from '@/test/fixtures/api-fixtures'
import { baseRoutes, mockFetch } from '@/test/mock-api'
import { renderApp } from '@/test/test-utils'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

const session = {
  isAuthenticated: true,
  user: { displayName: 'Ada Researcher', email: 'ada@example.org' },
  csrfToken: 'token',
}
const created = { ...rawFixtures.comparison, id: '5a1f3a7e-3c1c-4f43-9f0e-2f4d7a9b6c11' }

describe('Strategy Evaluation page', () => {
  it('sends the chosen profile once and opens the 3D analysis page', async () => {
    const api = mockFetch(
      baseRoutes({
        'GET /api/v1/auth/session': { body: session },
        'POST /api/v1/comparisons': { status: 201, body: created },
        [`GET /api/v1/comparisons/${created.id}`]: { body: created },
      }),
    )
    const user = userEvent.setup()
    const { router } = renderApp('/app/simulation/new?profile=0100000')

    await user.click(await screen.findByRole('button', { name: 'Review Analysis' }))
    await user.click(screen.getByRole('button', { name: 'Run Analysis' }))

    await waitFor(() =>
      expect(router.state.location.pathname).toBe(`/app/simulation/${created.id}`),
    )
    expect(await screen.findByRole('heading', { name: 'Resistance Trajectory' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Urinary Tract' })).toBeInTheDocument()
    expect(api.callsTo('POST /api/v1/comparisons')).toHaveLength(1)
    expect(api.callsTo('POST /api/v1/comparisons')[0]?.body).toEqual({
      resistanceProfile: [0, 1, 0, 0, 0, 0, 0],
    })
  })
})
