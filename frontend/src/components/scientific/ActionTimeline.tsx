import type { AntibioticEntry } from '@/domain/antibiotics'
import { drugLabel } from '@/domain/antibiotics'
import { formatProbability } from '@/domain/formatters'
import { GLOSSARY, outcomeLabel, terminationLabel, transitionSupportLabel } from '@/domain/terminology'
import type { StepTrace } from '@/domain/types'
import { StatusIndicator } from '@/components/ui/StatusIndicator'
import { cx } from '@/components/ui/cx'
import styles from './scientific.module.css'

export interface ActionTimelineProps {
  title: string
  /** Column heading for the action: "PPO-selected action" or "Sampled susceptible action". */
  selectionLabel: string
  steps: readonly StepTrace[]
  terminationReason: string
  antibiotics?: readonly AntibioticEntry[] | undefined
  selectedStep?: number | null
  onSelectStep?: (step: number) => void
}

function changeSummary(step: StepTrace, antibiotics: readonly AntibioticEntry[] | undefined): string {
  const parts: string[] = []
  if (step.newlyResistantAntibiotics.length > 0) {
    parts.push(`Newly resistant: ${step.newlyResistantAntibiotics.map((name) => drugLabel(antibiotics, name)).join(', ')}`)
  }
  if (step.newlySusceptibleAntibiotics.length > 0) {
    parts.push(`Newly susceptible: ${step.newlySusceptibleAntibiotics.map((name) => drugLabel(antibiotics, name)).join(', ')}`)
  }
  if (parts.length === 0) {
    parts.push('Resistance profile unchanged')
  }
  return parts.join('. ')
}

/**
 * One row per step, with the three concepts in separate columns: the selected action, whether the simulator has
 * transition data for it, and what the simulator then did.
 */
export function ActionTimeline({ title, selectionLabel, steps, terminationReason, antibiotics, selectedStep, onSelectStep }: ActionTimelineProps) {
  if (steps.length === 0) {
    return (
      <div className={styles['notice']} role="note">
        <div className={styles['noticeBody']}>
          <strong>{title}: no steps were taken</strong>
          <p>
            {terminationLabel(terminationReason)}.{' '}
            {terminationReason === 'no_effective_antibiotic' ? GLOSSARY.noFeasibleActions : ''}
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className={styles['tableWrap']}>
      <table className={styles['table']}>
        <caption>{title}</caption>
        <thead>
          <tr>
            <th scope="col">Step</th>
            <th scope="col">{selectionLabel}</th>
            <th scope="col">Transition support</th>
            <th scope="col">Observed simulated outcome</th>
          </tr>
        </thead>
        <tbody>
          {steps.map((step) => {
            const stepNumber = step.treatmentStepAfter
            const selected = selectedStep === stepNumber
            return (
              <tr key={step.stepIndex} className={cx(selected && styles['rowSelected'])} aria-current={selected ? 'step' : undefined}>
                <th scope="row">
                  {onSelectStep ? (
                    <button
                      type="button"
                      className={styles['stepButton']}
                      aria-pressed={selected}
                      aria-label={`Select step ${stepNumber}`}
                      onClick={() => onSelectStep(stepNumber)}
                    >
                      {stepNumber}
                    </button>
                  ) : (
                    stepNumber
                  )}
                </th>
                <td>
                  <div className={styles['cellStack']}>
                    <strong>{drugLabel(antibiotics, step.antibiotic)}</strong>
                    <StatusIndicator
                      kind={step.selectedDrugSusceptible ? 'susceptible' : 'resistant'}
                      label={step.selectedDrugSusceptible ? 'Susceptible' : 'Resistant'}
                      title={GLOSSARY.feasible}
                    />
                  </div>
                </td>
                <td>
                  <StatusIndicator
                    kind={step.hasCandidateTransition ? 'supported' : 'unsupported'}
                    label={transitionSupportLabel(step.hasCandidateTransition)}
                    title={step.hasCandidateTransition ? GLOSSARY.supported : GLOSSARY.unsupported}
                  />
                </td>
                <td>
                  <div className={styles['cellStack']}>
                    <span>{outcomeLabel(step)}</span>
                    <span className="muted">{changeSummary(step, antibiotics)}</span>
                    <span className="muted tabular">
                      Resistant count {step.resistantCountAfter} of 7
                      {step.selectedCandidateProbability === null
                        ? ''
                        : ` \u00b7 sampled outcome probability ${formatProbability(step.selectedCandidateProbability)}`}
                    </span>
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
