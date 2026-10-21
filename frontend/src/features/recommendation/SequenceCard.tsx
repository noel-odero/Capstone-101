import { FiCheck, FiInfo } from 'react-icons/fi'
import { Card, CardHeader } from '@/components/ui/Card'
import { drugLabel } from '@/domain/antibiotics'
import type { AntibioticEntry } from '@/domain/antibiotics'
import type { ResistanceProfile, StepTrace } from '@/domain/types'
import styles from './recommendation.module.css'

export interface SequenceCardProps {
  title: string
  badge?: string
  highlighted?: boolean
  initialProfile: ResistanceProfile
  steps: readonly StepTrace[]
  terminationReason: string
  antibiotics: readonly AntibioticEntry[]
  selectedStep: number
  onSelectStep: (step: number) => void
}
export function SequenceCard({
  title,
  highlighted = false,
  steps,
  antibiotics,
  selectedStep,
  onSelectStep,
}: SequenceCardProps) {
  const ordered = [...steps].sort((a, b) => a.treatmentStepAfter - b.treatmentStepAfter)
  return (
    <Card className={styles['sequenceListCard']} aria-label={title}>
      <CardHeader title={highlighted ? 'Top Recommendation' : title} />
      <ol className={styles['sequenceList']} aria-label={title}>
        {ordered.map((step, index) => (
          <li key={step.stepIndex}>
            <button
              type="button"
              aria-pressed={selectedStep === step.treatmentStepAfter}
              onClick={() => onSelectStep(step.treatmentStepAfter)}
            >
              <span className={styles['sequenceNumber']}>{index + 1}</span>
              <span>
                <strong>{drugLabel(antibiotics, step.antibiotic)}</strong>
                {highlighted && index === 0 ? <em>PPO-selected</em> : null}
                <small>
                  {step.hasCandidateTransition
                    ? 'Transition data available'
                    : 'No candidate transition data'}{' '}
                  <span>·</span> Step {step.treatmentStepAfter}
                </small>
              </span>
            </button>
          </li>
        ))}
        {!ordered.length ? (
          <li className={styles['noSequence']}>No feasible actions remain for this profile.</li>
        ) : null}
      </ol>
    </Card>
  )
}
export function SequenceExplanation() {
  return (
    <div className={styles['explanation']}>
      <Card>
        <CardHeader title="Why this sequence?" />
        <ul className={styles['reasons']}>
          <li>
            <FiCheck /> Selects from susceptible antibiotics
          </li>
          <li>
            <FiCheck /> Considers the evolving resistance profile
          </li>
          <li>
            <FiCheck /> Uses a frozen reinforcement learning policy
          </li>
          <li>
            <FiCheck /> Makes each simulated step inspectable
          </li>
        </ul>
      </Card>
      <Card>
        <div className={styles['explanationNote']}>
          <FiInfo size={22} />
          <p>
            This sequence is based on your starting resistance profile and simulated outcomes using
            our reinforcement learning model. It is a research output, not a treatment
            recommendation.
          </p>
        </div>
      </Card>
    </div>
  )
}
