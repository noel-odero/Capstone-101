import { screen, waitFor, within } from '@testing-library/react'
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
  it('rejects an existing label regardless of case and surrounding spaces', async () => {
    const api = mockFetch(
      baseRoutes({
        'GET /api/v1/auth/session': { body: session },
        'GET /api/v1/samples': { body: [sample] },
      }),
    )
    const user = userEvent.setup()
    renderApp('/app/samples')
    await screen.findByRole('heading', { name: sample.label })
    await user.type(screen.getByLabelText('Sample label'), '  uti-024  ')
    expect(screen.getByRole('alert')).toHaveTextContent('A sample with this label already exists.')
    expect(screen.getByRole('button', { name: 'Save sample' })).toBeDisabled()
    expect(api.callsTo('POST /api/v1/samples')).toHaveLength(0)
    await user.clear(screen.getByLabelText('Sample label'))
    await user.type(screen.getByLabelText('Sample label'), 'UTI-025')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save sample' })).toBeEnabled()
  })

  it('shows a duplicate-label error returned by the server when the local library is stale', async () => {
    mockFetch(
      baseRoutes({
        'GET /api/v1/auth/session': { body: session },
        'POST /api/v1/samples': {
          status: 422,
          body: {
            status: 422,
            code: 'sample_label_exists',
            detail: 'A sample with this label already exists.',
          },
        },
      }),
    )
    const user = userEvent.setup()
    renderApp('/app/samples')
    await user.type(await screen.findByLabelText('Sample label'), sample.label)
    await user.click(screen.getByRole('button', { name: 'Save sample' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'A sample with this label already exists.',
    )
    expect(screen.getByLabelText('Sample label')).toHaveValue(sample.label)
    await user.type(screen.getByLabelText('Sample label'), '-new')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('requires confirmation before deleting an analyzed sample and refreshes the library', async () => {
    let saved: SavedSample[] = [
      {
        ...sample,
        runs: [
          {
            id: rawFixtures.comparison.id,
            createdAtUtc: sample.addedAtUtc,
          },
        ],
      },
    ]
    const api = mockFetch(
      baseRoutes({
        'GET /api/v1/auth/session': { body: session },
        'GET /api/v1/samples': () => ({ body: saved }),
        [`DELETE /api/v1/samples/${sample.id}`]: () => {
          saved = []
          return { status: 204 }
        },
      }),
    )
    const user = userEvent.setup()
    renderApp('/app/samples')
    await user.click(await screen.findByRole('button', { name: `Delete ${sample.label}` }))
    const confirmation = screen.getByRole('group', { name: `Delete ${sample.label}?` })
    expect(confirmation).toHaveTextContent('Saved analyses will stay in Analysis History.')
    await user.click(within(confirmation).getByRole('button', { name: 'Cancel' }))
    expect(api.callsTo(`DELETE /api/v1/samples/${sample.id}`)).toHaveLength(0)
    await user.click(screen.getByRole('button', { name: `Delete ${sample.label}` }))
    await user.click(screen.getByRole('button', { name: 'Delete sample' }))
    await waitFor(() =>
      expect(screen.queryByRole('heading', { name: sample.label })).not.toBeInTheDocument(),
    )
    expect(
      screen
        .getAllByRole('status')
        .some((status) => status.textContent?.includes('Sample deleted.')),
    ).toBe(true)
    expect(api.callsTo(`DELETE /api/v1/samples/${sample.id}`)).toHaveLength(1)
  })

  it('retains the sample and shows an error if deletion fails', async () => {
    mockFetch(
      baseRoutes({
        'GET /api/v1/auth/session': { body: session },
        'GET /api/v1/samples': { body: [sample] },
        [`DELETE /api/v1/samples/${sample.id}`]: {
          status: 503,
          body: {
            status: 503,
            detail: 'The database is temporarily unavailable.',
          },
        },
      }),
    )
    const user = userEvent.setup()
    renderApp('/app/samples')
    await user.click(await screen.findByRole('button', { name: `Delete ${sample.label}` }))
    await user.click(screen.getByRole('button', { name: 'Delete sample' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Sample could not be deleted')
    expect(screen.getByRole('heading', { name: sample.label })).toBeInTheDocument()
  })

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
    await waitFor(
      () => expect(router.state.location.pathname).toBe(`/app/simulation/${created.id}`),
      { timeout: 5_000 },
    )
    expect(api.callsTo('POST /api/v1/comparisons')[0]?.body).toEqual({
      sampleId: sample.id,
      resistanceProfile: sample.resistanceProfile,
    })
  })
})
