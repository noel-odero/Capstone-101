import { render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { fixtures } from '@/test/fixtures/api-fixtures'
import { useProfileRun } from '@/features/profile/useProfileRun'
import { HomeMetrics } from './HomeMetrics'

vi.mock('@/features/profile/useProfileRun', () => ({ useProfileRun: vi.fn() }))

describe('Latest experiment metrics', () => {
  it('shows returned burden and susceptible action rate without implying clinical effectiveness', () => {
    const ppo = fixtures.comparison.ppo
    const summary = fixtures.recentRuns.items[0]
    if (!ppo || !summary) throw new Error('Captured comparison fixture is incomplete')
    vi.mocked(useProfileRun).mockReturnValue({
      status: 'ready',
      run: {
        summary,
        provenance: fixtures.comparison.provenance,
        ppo,
        baseline: fixtures.comparison.baseline,
      },
    })
    render(<HomeMetrics />)
    const card = screen.getByRole('heading', { name: 'Susceptible action rate' }).closest('article')
    if (!card) throw new Error('Metric card is missing')
    expect(
      within(card).getByText(`${Math.round((ppo.metrics.susceptibleActionRate ?? 0) * 100)}%`),
    ).toBeVisible()
    expect(screen.getByText(ppo.metrics.cumulativeResistanceBurden.toFixed(2))).toBeVisible()
    expect(screen.queryByText('Effective Treatments')).not.toBeInTheDocument()
    expect(screen.queryByText(/vs\. last simulation/)).not.toBeInTheDocument()
  })

  it('does not fabricate zero outcomes for an empty workspace', () => {
    vi.mocked(useProfileRun).mockReturnValue({ status: 'empty' })
    render(<HomeMetrics />)
    expect(screen.getAllByText('\u2014')).toHaveLength(4)
    expect(screen.getAllByText('Run an experiment to see results')).toHaveLength(4)
  })

  it('announces loading separately from an empty result', () => {
    vi.mocked(useProfileRun).mockReturnValue({ status: 'loading' })
    render(<HomeMetrics />)
    expect(screen.getByRole('region', { name: 'Latest PPO simulation' })).toHaveAttribute(
      'aria-busy',
      'true',
    )
    expect(screen.getAllByText('Loading latest run')).toHaveLength(4)
  })
})
