import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { fixtures } from '@/test/fixtures/api-fixtures'
import { baseRoutes, mockFetch } from '@/test/mock-api'
import { renderApp } from '@/test/test-utils'
import { validSelection, type HistoryComparison, type SavedAnalysis } from './history-api'
import { matchesInvestigation, summarizeEvidence } from './insight-data'
import { evidenceReport, metricsCsv } from './insight-export'

const session = {
  isAuthenticated: true,
  user: { displayName: 'Researcher', email: 'research@example.org' },
  csrfToken: 'token',
}
const firstId = '08f2732d-6b79-44ed-9fbd-79fd472804ac'
const secondId = '08f2732d-6b79-44ed-9fbd-79fd472804ad'
const run = fixtures.comparison
const ppo = run.ppo
const baseline = run.baseline
if (!ppo || !baseline) throw new Error('Expected complete comparison fixture')
const first: SavedAnalysis = {
  id: firstId,
  kind: 'comparison',
  createdAtUtc: run.createdAtUtc,
  initialProfile: ppo.initialProfile,
  provenance: run.provenance,
  seedConfiguration: run.seedConfiguration,
  strategies: [ppo, baseline],
  metricDefinitions: run.metricDefinitions,
  comparisonVerified: true,
  sampleId: null,
}
const second: SavedAnalysis = {
  ...first,
  id: secondId,
  strategies: [
    ...first.strategies,
    { ...ppo, strategy: 'dqn', metrics: { ...ppo.metrics, cumulativeResistanceBurden: 0 } },
  ],
}
const response: HistoryComparison = {
  analyses: [first, second],
  compatibility: {
    status: 'exploratory',
    issues: [
      {
        code: 'dqn_unavailable',
        severity: 'availability',
        message: 'DQN is unavailable in older records; missing results are not zero.',
        analysisIds: [firstId],
      },
    ],
  },
  burdenDifferences: [
    { analysisId: firstId, ppoMinusDqn: null, ppoMinusBaseline: -1, dqnMinusBaseline: null },
    {
      analysisId: secondId,
      ppoMinusDqn: ppo.metrics.cumulativeResistanceBurden,
      ppoMinusBaseline: -1,
      dqnMinusBaseline: -2,
    },
  ],
  interpretation: 'Descriptive saved records. No pooled performance statistic is calculated.',
}

function summary(record: SavedAnalysis) {
  return {
    ...record,
    status: 'completed',
    modelId: record.provenance.modelId,
    strategies: record.strategies.map((result) => ({ ...result, ...result.metrics })),
  }
}

describe('Analysis Insights', () => {
  it('retains selection across pages and filters, and reads saved records without running a policy', async () => {
    const api = mockFetch(
      baseRoutes({
        'GET /api/v1/auth/session': { body: session },
        'GET /api/v1/analyses': (call) => {
          const page = Number(new URLSearchParams(call.search).get('page'))
          return {
            body: {
              items: [summary(page === 2 ? second : first)],
              page,
              pageSize: 1,
              totalCount: 2,
            },
          }
        },
        'POST /api/v1/analyses/compare': { body: response },
      }),
    )
    const user = userEvent.setup()
    renderApp('/app/insights?ids=&tab=evidence')
    await user.click(await screen.findByRole('button', { name: 'Choose analyses for insights' }))
    await user.click(await screen.findByRole('checkbox', { name: `Select analysis ${firstId}` }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(await screen.findByRole('checkbox', { name: `Select analysis ${secondId}` }))
    await user.type(screen.getByLabelText('Exact profile'), '0100000')
    await user.selectOptions(screen.getByLabelText('Initially resistant'), '1')
    await user.click(screen.getByRole('button', { name: 'Apply filters' }))
    await waitFor(() =>
      expect(
        api.callsTo('GET /api/v1/analyses').some((call) => call.search.includes('profile=0100000')),
      ).toBe(true),
    )
    await user.click(screen.getByRole('button', { name: 'Update insights' }))
    await screen.findByRole('heading', { name: 'Policy outcomes' })
    expect(api.callsTo('POST /api/v1/analyses/compare')[0]?.body).toEqual({
      analysisIds: [firstId, secondId],
    })
    expect(api.callsTo('POST /api/v1/comparisons')).toHaveLength(0)
    expect(api.callsTo('POST /api/v1/simulations')).toHaveLength(0)
  })

  it('shows missing DQN separately from zero, comparison limits, and recorded traces', async () => {
    mockFetch(
      baseRoutes({
        'GET /api/v1/auth/session': { body: session },
        'POST /api/v1/analyses/compare': { body: response },
      }),
    )
    const user = userEvent.setup()
    renderApp(`/app/insights?ids=${firstId},${secondId}&tab=evidence`)
    const table = await screen.findByRole('table', {
      name: 'Selected research evidence',
    })
    const rows = within(table).getAllByRole('row')
    const missingRow = rows[1]
    const completeRow = rows[2]
    if (!missingRow || !completeRow) throw new Error('Expected two saved analyses')
    expect(within(missingRow).getAllByText('Unavailable')).toHaveLength(1)
    expect(within(completeRow).getByText('0.00')).toBeInTheDocument()
    await user.click(screen.getByText('Exploratory evidence'))
    expect(screen.getByText(/DQN is unavailable in older records/)).toBeVisible()
    await user.click(screen.getByRole('button', { name: `Inspect analysis ${firstId}` }))
    expect(screen.getByRole('heading', { name: 'Recorded action sequences' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open 3D evaluation' })).toHaveAttribute(
      'href',
      `/app/simulation/${firstId}`,
    )
    expect(screen.getByText('Transition support')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Close details' }))
    await user.selectOptions(screen.getByLabelText('Investigate'), 'dqn_worse')
    expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(1)
  })

  it('rejects malformed, duplicate and oversized selections before requesting saved records', async () => {
    for (const value of [
      '',
      firstId,
      `${firstId},${firstId}`,
      `${firstId},bad`,
      `${firstId},${firstId.toUpperCase()}`,
    ])
      expect(validSelection(value)).toBe(false)
    const api = mockFetch(baseRoutes({ 'GET /api/v1/auth/session': { body: session } }))
    renderApp(`/app/history/analyze?ids=${firstId},bad`)
    await screen.findByText('Start with a research question')
    expect(api.callsTo('POST /api/v1/analyses/compare')).toHaveLength(0)
  })

  it('keeps a missing or foreign record error visible instead of silently dropping it', async () => {
    mockFetch(
      baseRoutes({
        'GET /api/v1/auth/session': { body: session },
        'POST /api/v1/analyses/compare': {
          status: 404,
          body: {
            status: 404,
            code: 'analysis_not_found',
            title: 'One or more selected analyses are unavailable.',
          },
        },
      }),
    )
    renderApp(`/app/history/analyze?ids=${firstId},${secondId}`)
    await screen.findByText('Selected analyses could not be loaded')
    expect(screen.queryByRole('heading', { name: 'Policy outcomes' })).not.toBeInTheDocument()
  })

  it('separates recorded failure cases and evidence gaps without treating missing DQN as a failure', () => {
    const failed = {
      ...second,
      strategies: second.strategies.map((result) => ({
        ...result,
        metrics: {
          ...result.metrics,
          cumulativeResistanceBurden: result.strategy === 'random_susceptible_baseline' ? 1 : 2,
        },
      })),
    }
    expect(matchesInvestigation(failed, 'baseline_lower')).toBe(true)
    expect(matchesInvestigation(failed, 'ppo_worse')).toBe(true)
    expect(matchesInvestigation(failed, 'dqn_worse')).toBe(true)
    expect(matchesInvestigation(first, 'dqn_worse')).toBe(false)
    expect(matchesInvestigation({ ...failed, comparisonVerified: false }, 'baseline_lower')).toBe(
      false,
    )
    const summary = summarizeEvidence([first, failed])
    expect(summary.paired).toHaveLength(1)
    const disjoint = summarizeEvidence([
      { ...first, strategies: first.strategies.filter((result) => result.strategy === 'ppo') },
      { ...second, strategies: second.strategies.filter((result) => result.strategy === 'dqn') },
    ])
    expect(disjoint.profiles[0]?.hasRepeatedPolicy).toBe(false)
    expect(summary.totalSteps).toBe(
      first.strategies.reduce((sum, result) => sum + result.metrics.treatmentSteps, 0) +
        failed.strategies.reduce((sum, result) => sum + result.metrics.treatmentSteps, 0),
    )
  })

  it('exports traceable reports safely and leaves missing strategy measurements out of the metric CSV', () => {
    const report = evidenceReport(response, '<script>bad()</script>', 'Why do the policies differ?')
    expect(report).not.toContain('<script>bad()')
    expect(report).toContain('&lt;script&gt;')
    expect(report).toContain(first.provenance.interactionDataSha256)
    expect(report).toContain('No applicable data')
    expect(metricsCsv(response).split('\r\n')).toHaveLength(6)
    expect(metricsCsv(response)).toContain(firstId)
  })

  it('saves a research question to an account-backed collection and reopens its exact selection', async () => {
    const saved: {
      id: string
      name: string
      question: string
      createdAtUtc: string
      analysisIds: string[]
    }[] = []
    const api = mockFetch(
      baseRoutes({
        'GET /api/v1/auth/session': { body: session },
        'POST /api/v1/analyses/compare': { body: response },
        'GET /api/v1/analysis-collections': () => ({ body: saved }),
        'POST /api/v1/analysis-collections': (call) => {
          saved.push({
            id: '08f2732d-6b79-44ed-9fbd-79fd472804ae',
            createdAtUtc: run.createdAtUtc,
            ...(call.body as { name: string; question: string; analysisIds: string[] }),
          })
          return { status: 201, body: saved[0] }
        },
      }),
    )
    const user = userEvent.setup()
    const { router } = renderApp(`/app/insights?ids=${firstId},${secondId}&tab=collections`)
    await user.type(await screen.findByLabelText('Collection name'), 'Policy disagreement')
    await user.type(
      screen.getByLabelText('Research question'),
      'Which actions explain different burdens?',
    )
    await user.click(screen.getByRole('button', { name: 'Save collection' }))
    expect(await screen.findByRole('heading', { name: 'Policy disagreement' })).toBeInTheDocument()
    expect(api.callsTo('POST /api/v1/analysis-collections')[0]?.body).toMatchObject({
      analysisIds: [firstId, secondId],
    })
    await user.click(screen.getByRole('button', { name: 'Open collection' }))
    await screen.findByRole('heading', { name: 'Policy outcomes' })
    expect(router.state.location.search).toContain('collection=')
    expect(screen.getByText('Which actions explain different burdens?')).toBeInTheDocument()
  })
})
