import { MetricDefinitionsTable } from '@/components/scientific/OutcomeSummary'
import { SimulationRunHeader } from '@/components/scientific/SimulationRunHeader'
import { StepInspector } from '@/components/scientific/StepInspector'
import { Disclosure } from '@/components/ui/Disclosure'
import type { AntibioticEntry } from '@/domain/antibiotics'
import { formatStep } from '@/domain/formatters'
import { lastStepOf } from '@/domain/trajectory'
import { STRATEGY_NAMES } from '@/domain/terminology'
import type { Comparison, StrategyResult } from '@/domain/types'
import styles from './simulation.module.css'

export interface StepDetailsProps {
  comparison: Comparison
  ppo: StrategyResult
  baseline: StrategyResult
  antibiotics: readonly AntibioticEntry[]
  selectedStep: number
  onSelectStep: (step: number) => void
}

/** The scientific detail behind the picture, kept one click away: state, action, transition support and outcome per step. */
export function StepDetails({ comparison, ppo, baseline, antibiotics, selectedStep, onSelectStep }: StepDetailsProps) {
  const lastStep = lastStepOf(ppo.steps, baseline.steps)
  return (
    <div className={styles['details']}>
      <Disclosure summary={`Step details: ${formatStep(selectedStep)}`}>
        <div className="stack-lg">
          <ol className={styles['stepChips']} aria-label="Choose a step">
            {Array.from({ length: lastStep + 1 }, (_, step) => (
              <li key={step}>
                <button type="button" className={styles['stepChip']} aria-pressed={selectedStep === step} aria-label={step === 0 ? 'Step 0, initial state' : `Step ${step}`} onClick={() => onSelectStep(step)}>
                  {step}
                </button>
              </li>
            ))}
          </ol>
          <div className={styles['detailColumns']}>
            <StepInspector
              heading={STRATEGY_NAMES.ppo}
              selectionLabel="PPO-selected action"
              strategyName={STRATEGY_NAMES.ppo}
              initialProfile={ppo.initialProfile}
              steps={ppo.steps}
              terminationReason={ppo.terminationReason}
              step={selectedStep}
              antibiotics={antibiotics}
            />
            <StepInspector
              heading={STRATEGY_NAMES.random_susceptible_baseline}
              selectionLabel="Sampled susceptible action"
              strategyName={STRATEGY_NAMES.random_susceptible_baseline}
              initialProfile={baseline.initialProfile}
              steps={baseline.steps}
              terminationReason={baseline.terminationReason}
              step={selectedStep}
              antibiotics={antibiotics}
            />
          </div>
        </div>
      </Disclosure>
      <Disclosure summary="Metric definitions">
        <MetricDefinitionsTable
          definitions={comparison.metricDefinitions}
          columns={[
            { label: STRATEGY_NAMES.ppo, metrics: ppo.metrics },
            { label: 'Baseline', metrics: baseline.metrics },
          ]}
        />
      </Disclosure>
      <Disclosure summary="Run details and reproducibility">
        <div className="stack">
          <SimulationRunHeader
            runId={comparison.id}
            kindLabel="Comparison"
            status={comparison.status}
            isPersisted={comparison.isPersisted}
            createdAtUtc={comparison.createdAtUtc}
            provenance={comparison.provenance}
            seedConfiguration={comparison.seedConfiguration}
            initialProfile={ppo.initialProfile}
          />
          <p className="muted">{comparison.singleRunCaveat}</p>
          <p className="muted">{comparison.pairingSemantics}</p>
        </div>
      </Disclosure>
    </div>
  )
}
