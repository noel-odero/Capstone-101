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
  it('shows all three orders and lets each learned policy be inspected and compared', async () => {
    const user = userEvent.setup()
    const dqn = strategyResultSchema.parse({ ...ppoResult, strategy: 'dqn', displayLabel: 'DQN' })
    render(
      <ResultsWorkbench
        run={{ ...run, dqn }}
        ppo={ppoResult}
        baseline={baselineResult}
        antibiotics={antibiotics}
        comparisonId={run.id}
      />,
    )
    expect(screen.getByRole('heading', { name: 'Results and Recommendations' })).toBeInTheDocument()
    expect(screen.getByText('PPO + DQN · same sequence')).toBeInTheDocument()
    const dqnOrder = screen.getByRole('region', { name: 'DQN antibiotic order' })
    const firstDqn = within(dqnOrder).getAllByRole('button')[0]
    if (!firstDqn) throw new Error('Expected a DQN step')
    await user.click(firstDqn)
    expect(
      within(screen.getByRole('region', { name: 'Decision trace' })).getByText(/DQN.*Step 1/),
    ).toBeInTheDocument()
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
    const table = screen.getByRole('table', { name: 'Independent simulation outcome metrics' })
    expect(within(table).getByRole('columnheader', { name: 'DQN' })).toBeInTheDocument()
    expect(within(table).getByRole('columnheader', { name: 'Random baseline' })).toBeInTheDocument()
    expect(
      within(table).queryByRole('rowheader', { name: /Mask compliance/ }),
    ).not.toBeInTheDocument()
    await user.click(screen.getByText('Constraint checks and run length'))
    const constraints = screen.getByRole('table', { name: 'Simulation constraint checks' })
    const exposure = within(constraints)
      .getByRole('rowheader', { name: /Antibiotic exposure/ })
      .closest('tr')
    if (!exposure) throw new Error('Expected an exposure row')
    expect(
      within(exposure)
        .getAllByRole('cell')
        .map((cell) => cell.textContent),
    ).toEqual([
      String(ppoResult.metrics.cumulativeAntibioticExposure),
      String(dqn.metrics.cumulativeAntibioticExposure),
      String(baselineResult.metrics.cumulativeAntibioticExposure),
    ])
    expect(screen.getByRole('tab', { name: 'Compare' })).toHaveAttribute('aria-selected', 'true')
  })

  it('keeps older two-strategy comparisons readable without inventing DQN results', () => {
    render(
      <ResultsWorkbench
        run={run}
        ppo={ppoResult}
        baseline={baselineResult}
        antibiotics={antibiotics}
        comparisonId={run.id}
      />,
    )
    expect(screen.queryByRole('region', { name: 'DQN antibiotic order' })).not.toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'PPO antibiotic order' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Run with DQN' })).toHaveAttribute(
      'href',
      `/app/simulation/new?profile=${run.ppo?.initialProfile.join('')}`,
    )
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
