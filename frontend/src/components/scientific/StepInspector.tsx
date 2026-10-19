import type { AntibioticEntry } from '@/domain/antibiotics'
import { drugLabel } from '@/domain/antibiotics'
import { formatProbability, formatStep } from '@/domain/formatters'
import { formatMetricValue } from '@/domain/metrics'
import { GLOSSARY, outcomeLabel, terminationLabel, transitionSupportLabel } from '@/domain/terminology'
import type { ResistanceProfile, StepTrace } from '@/domain/types'
import { StatusIndicator } from '@/components/ui/StatusIndicator'
import { countResistant, countSusceptible } from '@/domain/profile'
import { ResistanceProfileGrid } from './ResistanceProfileGrid'
import { TransitionSupportNotice } from './TransitionSupportNotice'
import styles from './scientific.module.css'

export interface StepInspectorProps {
  heading: string
  /** Wording for the action: "PPO-selected action" or "Sampled susceptible action". */
  selectionLabel: string
  strategyName: string
  initialProfile: ResistanceProfile
  steps: readonly StepTrace[]
  terminationReason: string
  /** Treatment step to show: 0 is the initial state, 1 to N follow an action. */
  step: number
  antibiotics: readonly AntibioticEntry[] | undefined
}

function stateAt(initialProfile: ResistanceProfile, steps: readonly StepTrace[], step: number): ResistanceProfile | null {
  if (step === 0) {
    return initialProfile
  }
  return steps.find((candidate) => candidate.treatmentStepAfter === step)?.resistanceProfileAfter ?? null
}

/**
 * The state, action, transition support and observed outcome for one step of one strategy. Everything shown is a
 * returned value; nothing is inferred. A step beyond the end of a shorter episode is reported as such.
 */
export function StepInspector({
  heading,
  selectionLabel,
  strategyName,
  initialProfile,
  steps,
  terminationReason,
  step,
  antibiotics,
}: StepInspectorProps) {
  const profile = stateAt(initialProfile, steps, step)
  const trace = step === 0 ? undefined : steps.find((candidate) => candidate.treatmentStepAfter === step)
  const lastStep = steps.length === 0 ? 0 : Math.max(...steps.map((candidate) => candidate.treatmentStepAfter))

  if (profile === null) {
    return (
      <section className="stack" aria-label={`${heading}, ${formatStep(step)}`}>
        <h3>{heading}</h3>
        <div className={styles['notice']} role="note">
          <div className={styles['noticeBody']}>
            <strong>This episode ended after step {lastStep}</strong>
            <p>{terminationLabel(terminationReason)}. There is no state to show for step {step}.</p>
          </div>
        </div>
      </section>
    )
  }

  const before = step === 0 ? null : (stateAt(initialProfile, steps, step - 1) ?? null)
  const changed = new Set<number>()
  if (before) {
    profile.forEach((state, index) => {
      if (state !== before[index]) {
        changed.add(index)
      }
    })
  }

  return (
    <section className="stack" aria-label={`${heading}, ${formatStep(step)}`}>
      <h3>{heading}</h3>
      <p className="muted tabular">
        State after {formatStep(step).toLowerCase()}: {countResistant(profile)} resistant, {countSusceptible(profile)} susceptible
      </p>
      {antibiotics ? (
        <ResistanceProfileGrid
          label={`${strategyName} resistance profile, ${formatStep(step)}`}
          entries={antibiotics}
          profile={profile}
          changed={changed}
          compact
        />
      ) : null}
      {trace ? (
        <dl className={styles['summaryGrid']}>
          <div className={styles['summaryItem']}>
            <dt>{selectionLabel}</dt>
            <dd>{drugLabel(antibiotics, trace.antibiotic)}</dd>
          </div>
          <div className={styles['summaryItem']}>
            <dt>Susceptibility</dt>
            <dd>
              <StatusIndicator
                kind={trace.selectedDrugSusceptible ? 'susceptible' : 'resistant'}
                label={trace.selectedDrugSusceptible ? 'Susceptible' : 'Resistant'}
                title={GLOSSARY.feasible}
              />
            </dd>
          </div>
          <div className={styles['summaryItem']}>
            <dt>Transition support</dt>
            <dd>
              <StatusIndicator
                kind={trace.hasCandidateTransition ? 'supported' : 'unsupported'}
                label={transitionSupportLabel(trace.hasCandidateTransition)}
              />
            </dd>
          </div>
          <div className={styles['summaryItem']}>
            <dt>Observed simulated outcome</dt>
            <dd>{outcomeLabel(trace)}</dd>
          </div>
          <div className={styles['summaryItem']}>
            <dt>Step reward (simulator units)</dt>
            <dd>{formatMetricValue('cumulativeReward', trace.reward)}</dd>
          </div>
          {trace.hasCandidateTransition ? (
            <div className={styles['summaryItem']}>
              <dt>Sampled outcome probability</dt>
              <dd>{formatProbability(trace.selectedCandidateProbability)}</dd>
            </div>
          ) : null}
        </dl>
      ) : (
        <p className="muted">Initial state: no action has been taken yet.</p>
      )}
      {trace && trace.feasibleActions.length > 0 ? (
        <p className="muted">
          Feasible under the simulator&apos;s action mask at this step:{' '}
          {trace.feasibleActions.map((action) => drugLabel(antibiotics, action.antibiotic)).join(', ')}.
        </p>
      ) : null}
      {trace && !trace.hasCandidateTransition ? (
        <TransitionSupportNotice antibiotic={drugLabel(antibiotics, trace.antibiotic)} />
      ) : null}
      {trace?.terminationReason ? (
        <p>
          <StatusIndicator kind="info" label="Episode ended" /> {terminationLabel(trace.terminationReason)}
        </p>
      ) : null}
    </section>
  )
}
