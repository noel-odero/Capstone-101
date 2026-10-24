import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { baseRoutes, mockFetch } from '@/test/mock-api'
import { renderApp } from '@/test/test-utils'
import { rawFixtures } from '@/test/fixtures/api-fixtures'
import type { SavedSample } from './sample-api'

const session = {
  isAuthenticated: true,
  user: { displayName: 'Ada Researcher', email: 'ada@example.org' },
  csrfToken: 'token',
}
const sample: SavedSample = {
  id: '08f2732d-6b79-44ed-9fbd-79fd472804ac',
  label: 'UTI-024',
  addedAtUtc: '2026-10-22T08:30:00Z',
  resistanceProfile: [0, 1, 0, 0, 0, 0, 0],
  runs: [],
}

describe('sample workflow', () => {
  it('saves profiles without running analyses and resets for the next sample', async () => {
    const saved: SavedSample[] = []
    const api = mockFetch(
      baseRoutes({
        'GET /api/v1/auth/session': { body: session },
        'GET /api/v1/samples': () => ({ body: saved }),
        'POST /api/v1/samples': (call) => {
          saved.push({
            ...sample,
            ...(call.body as Pick<SavedSample, 'label' | 'resistanceProfile'>),
          })
          return { status: 201, body: saved[0] }
        },
      }),
    )
    const user = userEvent.setup()
    renderApp('/app/samples')
    await user.type(await screen.findByLabelText('Sample label'), 'UTI-024')
    await user.click(screen.getByRole('switch', { name: 'Nitrofurantoin resistant' }))
    await user.click(screen.getByRole('button', { name: 'Save sample' }))
    expect(await screen.findByRole('heading', { name: 'UTI-024' })).toBeInTheDocument()
    expect(api.callsTo('POST /api/v1/samples')[0]?.body).toEqual({
      label: 'UTI-024',
      resistanceProfile: sample.resistanceProfile,
    })
    expect(api.callsTo('POST /api/v1/comparisons')).toHaveLength(0)
    expect(screen.getByLabelText('Sample label')).toHaveValue('')
    expect(screen.getByRole('switch', { name: 'Nitrofurantoin resistant' })).toHaveAttribute(
      'aria-checked',
      'false',
    )
    expect(screen.getByRole('link', { name: 'New Analysis' })).toHaveAttribute(
      'href',
      `/app/simulation/new?sample=${sample.id}`,
    )
  })

  it('loads the saved profile by sample id and prevents silently changing it', async () => {
    const created = { ...rawFixtures.comparison, sampleId: sample.id }
    const api = mockFetch(
      baseRoutes({
        'GET /api/v1/auth/session': { body: session },
        [`GET /api/v1/samples/${sample.id}`]: { body: sample },
        'POST /api/v1/comparisons': { status: 201, body: created },
        [`GET /api/v1/comparisons/${created.id}`]: { body: created },
      }),
    )
    const user = userEvent.setup()
    const { router } = renderApp(`/app/simulation/new?sample=${sample.id}&profile=1111111`)
    expect(await screen.findByLabelText('Resistance profile code')).toHaveTextContent('0100000')
    expect(screen.getByText('UTI-024')).toBeInTheDocument()
    expect(await screen.findByRole('switch', { name: 'Ciprofloxacin resistant' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Reset' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Review Analysis' }))
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Review Analysis' })).toBeInTheDocument(),
    )
    expect(api.callsTo('POST /api/v1/comparisons')).toHaveLength(0)
    await user.click(screen.getByRole('button', { name: 'Run Analysis' }))
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(`/app/simulation/${created.id}`),
    )
    expect(api.callsTo('POST /api/v1/comparisons')[0]?.body).toEqual({
      sampleId: sample.id,
      resistanceProfile: sample.resistanceProfile,
    })
  })
})
