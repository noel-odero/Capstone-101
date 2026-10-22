import { buildCatalogue } from '@/domain/antibiotics'
import { antibioticCatalogueSchema, comparisonSchema, strategyResultSchema } from '@/domain/types'
import antibioticsJson from '@/test/fixtures/captured/antibiotics.json'
import comparisonJson from '@/test/fixtures/captured/comparison.json'
import { screen, within } from '@testing-library/react'
import { renderWithProviders as render } from '@/test/test-utils'
import userEvent from '@testing-library/user-event'

import { describe, expect, it } from 'vitest'
import { ResultsWorkbench } from './ResultsWorkbench'

const run = comparisonSchema.parse(comparisonJson)
const ppoResult = strategyResultSchema.parse(run.ppo)
const baselineResult = strategyResultSchema.parse(run.baseline)
const antibiotics = buildCatalogue(antibioticCatalogueSchema.parse(antibioticsJson))

describe('saved simulation results', () => {
  it('shows both orders, inspects the selected baseline step and compares actual metrics', async () => {
    const user = userEvent.setup()
    render(
      <ResultsWorkbench
        run={run}
        ppo={ppoResult}
        baseline={baselineResult}
        antibiotics={antibiotics}
        comparisonId={run.id}
      />,
    )
    expect(screen.getByRole('heading', { name: 'Results and Recommendations' })).toBeInTheDocument()
    const baseline = screen.getByRole('region', {
      name: 'Random Susceptible Baseline antibiotic order',
    })
    const buttons = within(baseline).getAllByRole('button')
    expect(buttons).toHaveLength(baselineResult.steps.length)
    const first = buttons[0]
    if (!first) throw new Error('Expected a baseline step')
    await user.click(first)
    const trace = screen.getByRole('region', { name: 'Decision trace' })
    expect(within(trace).getByText(/Random Susceptible Baseline.*Step 1/)).toBeInTheDocument()
    await user.click(within(trace).getByText('Transition evidence and assumptions'))
    expect(within(trace).getByText(/scenario-assumed, not empirical/)).toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: 'Compare' }))
    const table = screen.getByRole('table')
    expect(within(table).getByRole('columnheader', { name: 'Random baseline' })).toBeInTheDocument()
    const exposure = within(table)
      .getByRole('rowheader', { name: /Antibiotic exposure/ })
      .closest('tr')
    if (!exposure) throw new Error('Expected an exposure row')
    expect(
      within(exposure)
        .getAllByRole('cell')
        .map((cell) => cell.textContent),
    ).toEqual([
      String(ppoResult.metrics.cumulativeAntibioticExposure),
      String(baselineResult.metrics.cumulativeAntibioticExposure),
    ])
    expect(screen.getByRole('tab', { name: 'Compare' })).toHaveAttribute('aria-selected', 'true')
  })

  it('does not invent a comparator for a standalone PPO result', async () => {
    const user = userEvent.setup()
    const metadata = run
    render(
      <ResultsWorkbench
        run={{ ...metadata, result: ppoResult }}
        ppo={ppoResult}
        baseline={null}
        antibiotics={antibiotics}
        comparisonId={undefined}
      />,
    )
    expect(
      screen.queryByRole('region', { name: 'Random Susceptible Baseline antibiotic order' }),
    ).not.toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: 'Compare' }))
    expect(screen.getByText(/This saved run contains PPO only/)).toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: 'Random baseline' })).not.toBeInTheDocument()
  })
})
