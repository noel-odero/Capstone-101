import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import { buildCatalogue } from '@/domain/antibiotics'
import { allSusceptibleProfile } from '@/domain/profile'
import type { StrategyResult } from '@/domain/types'
import { fixtures } from '@/test/fixtures/api-fixtures'
import { ActionTimeline } from './ActionTimeline'
import { ResistanceProfileGrid } from './ResistanceProfileGrid'
import { ScientificLimitationsNotice } from './ScientificLimitationsNotice'
import { StepInspector } from './StepInspector'
import { TransitionSupportNotice } from './TransitionSupportNotice'

const entries = buildCatalogue(fixtures.antibiotics)
const ppo = fixtures.comparison.ppo as StrategyResult
const baseline = fixtures.comparison.baseline as StrategyResult

describe('ResistanceProfileGrid', () => {
  it('renders seven antibiotics in profile order with the state written out', () => {
    render(<ResistanceProfileGrid label="Profile" entries={entries} profile={[0, 1, 0, 0, 0, 0, 0]} />)
    const items = within(screen.getByRole('list', { name: 'Profile' })).getAllByRole('listitem')
    expect(items).toHaveLength(7)
    expect(items[0]).toHaveTextContent('Ciprofloxacin')
    expect(items[0]).toHaveTextContent('Susceptible')
    expect(items[1]).toHaveTextContent('Nitrofurantoin')
    expect(items[1]).toHaveTextContent('Resistant')
  })

  it('becomes a set of toggle buttons that report their state and flip on press', async () => {
    const onToggle = vi.fn()
    render(<ResistanceProfileGrid label="Profile" entries={entries} profile={allSusceptibleProfile()} onToggle={onToggle} />)
    const button = screen.getByRole('button', { name: /Ciprofloxacin: susceptible\. Press to mark resistant\./ })
    expect(button).toHaveAttribute('aria-pressed', 'false')
    await userEvent.setup().click(button)
    expect(onToggle).toHaveBeenCalledWith(0)
  })

  it('labels changed positions in words as well as with an outline', () => {
    render(<ResistanceProfileGrid label="Profile" entries={entries} profile={[0, 1, 0, 0, 0, 0, 0]} changed={new Set([1])} />)
    expect(screen.getByText(/Resistant · Changed/)).toBeInTheDocument()
  })
})

describe('TransitionSupportNotice', () => {
  it('separates "susceptible" from "supported" and refuses to call an unchanged profile a success', () => {
    render(<TransitionSupportNotice antibiotic="Gentamicin" />)
    const note = screen.getByRole('note')
    expect(note).toHaveTextContent('No supported transition data')
    expect(note).toHaveTextContent('Gentamicin is susceptible in this state, but the simulator has no candidate transition data for it.')
    expect(note).toHaveTextContent(/not evidence that the antibiotic worked/i)
  })

  it('summarises the steps without support for each strategy', () => {
    render(
      <TransitionSupportNotice
        summaries={[
          { strategyName: 'PPO', count: 8, total: 8 },
          { strategyName: 'Random Susceptible Baseline', count: 4, total: 8 },
        ]}
      />,
    )
    expect(screen.getByText('PPO: 8 of 8 selected actions had no supported transition data.')).toBeInTheDocument()
    expect(screen.getByText('Random Susceptible Baseline: 4 of 8 selected actions had no supported transition data.')).toBeInTheDocument()
  })
})

describe('ActionTimeline', () => {
  it('shows the selected action, transition support and observed outcome separately for every step', () => {
    render(<ActionTimeline title="PPO actions" selectionLabel="PPO-selected action" steps={ppo.steps} terminationReason={ppo.terminationReason} antibiotics={entries} />)
    const table = screen.getByRole('table', { name: 'PPO actions' })
    expect(within(table).getAllByRole('columnheader').map((header) => header.textContent)).toEqual([
      'Step',
      'PPO-selected action',
      'Transition support',
      'Observed simulated outcome',
    ])
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(8)
    expect(rows[0]).toHaveTextContent('Gentamicin')
    expect(rows[0]).toHaveTextContent('Susceptible')
    expect(rows[0]).toHaveTextContent('No supported transition data')
    expect(rows[0]).toHaveTextContent('profile unchanged')
  })

  it('distinguishes a supported step with a modeled outcome', () => {
    render(<ActionTimeline title="Baseline" selectionLabel="Sampled susceptible action" steps={baseline.steps} terminationReason={baseline.terminationReason} antibiotics={entries} />)
    const rows = screen.getAllByRole('row').slice(1)
    expect(rows[0]).toHaveTextContent('Trimethoprim')
    expect(rows[0]).toHaveTextContent('Transition data available')
    expect(rows[4]).toHaveTextContent(/Cross-resistance/)
    const newlyResistant = baseline.steps[4]?.newlyResistantAntibiotics ?? []
    expect(newlyResistant.length).toBeGreaterThan(0)
    expect(rows[4]).toHaveTextContent(`Newly resistant: ${newlyResistant.map((name) => entries.find((entry) => entry.name === name)?.displayName).join(', ')}`)
  })

  it('selects a step by button and marks it as current', async () => {
    const onSelect = vi.fn()
    render(<ActionTimeline title="PPO actions" selectionLabel="PPO-selected action" steps={ppo.steps} terminationReason={ppo.terminationReason} selectedStep={3} onSelectStep={onSelect} />)
    expect(screen.getByRole('button', { name: 'Select step 3' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.setup().click(screen.getByRole('button', { name: 'Select step 5' }))
    expect(onSelect).toHaveBeenCalledWith(5)
  })

  it('explains a run with no steps instead of rendering an empty table', () => {
    render(<ActionTimeline title="PPO actions" selectionLabel="PPO-selected action" steps={[]} terminationReason="no_effective_antibiotic" />)
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.getByRole('note')).toHaveTextContent('no steps were taken')
    expect(screen.getByRole('note')).toHaveTextContent('no action is feasible')
  })
})

describe('StepInspector', () => {
  const props = {
    selectionLabel: 'PPO-selected action',
    strategyName: 'PPO',
    initialProfile: ppo.initialProfile,
    steps: ppo.steps,
    terminationReason: ppo.terminationReason,
    antibiotics: entries,
  }

  it('shows the initial state for step 0 with no action', () => {
    render(<StepInspector heading="PPO" step={0} {...props} />)
    expect(screen.getByText(/Initial state: no action has been taken yet/)).toBeInTheDocument()
    expect(screen.queryByText('PPO-selected action')).not.toBeInTheDocument()
  })

  it('shows an unsupported step with the explicit data-gap warning', () => {
    render(<StepInspector heading="PPO" step={1} {...props} />)
    expect(screen.getByText('PPO-selected action')).toBeInTheDocument()
    expect(screen.getAllByText('Gentamicin').length).toBeGreaterThan(0)
    expect(screen.getByText('Susceptibility').nextElementSibling).toHaveTextContent('Susceptible')
    expect(screen.getAllByText('No supported transition data').length).toBeGreaterThan(0)
    expect(screen.getByText(/the simulator has no candidate transition data for it/i)).toBeInTheDocument()
    expect(screen.getByText(/Feasible under the simulator's action mask/)).toBeInTheDocument()
  })

  it('shows the observed change for a supported step with a modeled outcome', () => {
    render(<StepInspector heading="Baseline" {...props} strategyName="Baseline" selectionLabel="Sampled susceptible action" steps={baseline.steps} initialProfile={baseline.initialProfile} terminationReason={baseline.terminationReason} step={5} />)
    expect(screen.getByText('Transition data available')).toBeInTheDocument()
    expect(screen.getByText(/Cross-resistance: a target drug became resistant/)).toBeInTheDocument()
    expect(screen.getByText(/Resistant · Changed/)).toBeInTheDocument()
    expect(screen.getByText('Sampled outcome probability')).toBeInTheDocument()
  })

  it('reports that a shorter episode has ended rather than inventing a state', () => {
    render(<StepInspector heading="Baseline" {...props} steps={baseline.steps.slice(0, 3)} step={6} terminationReason="no_effective_antibiotic" />)
    expect(screen.getByText('This episode ended after step 3')).toBeInTheDocument()
    expect(screen.getByText(/There is no state to show for step 6/)).toBeInTheDocument()
  })
})

describe('ScientificLimitationsNotice', () => {
  it('states the research-prototype scope in its short form with a link to the full list', () => {
    render(
      <MemoryRouter>
        <ScientificLimitationsNotice />
      </MemoryRouter>,
    )
    expect(screen.getByRole('note')).toHaveTextContent(/not clinical treatment guidance/i)
    expect(screen.getByRole('link', { name: 'Scope and limitations' })).toHaveAttribute('href', '/limitations')
  })

  it('lists the limitations in the detailed form, including the data-gap and single-run caveats', () => {
    render(
      <MemoryRouter>
        <ScientificLimitationsNotice detailed id="limitations" />
      </MemoryRouter>,
    )
    const note = screen.getByRole('note')
    expect(note).toHaveAttribute('id', 'limitations')
    expect(note).toHaveTextContent(/single stochastic|one stochastic run/i)
    expect(note).toHaveTextContent(/data gap/i)
    expect(note).toHaveTextContent(/not an exhaustive or optimal search/i)
    expect(note).toHaveTextContent(/uses no patient data/i)
  })
})
