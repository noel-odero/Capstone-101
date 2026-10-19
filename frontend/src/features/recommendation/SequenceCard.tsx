import { StatusIndicator } from '@/components/ui/StatusIndicator'
import { SequenceMatrix } from '@/components/scientific/SequenceMatrix'
import { Card, CardHeader } from '@/components/ui/Card'
import { cx } from '@/components/ui/cx'
import type { AntibioticEntry } from '@/domain/antibiotics'
import { drugLabel } from '@/domain/antibiotics'
import { actionsFromSteps, profilesFromSteps } from '@/domain/trajectory'
import { terminationLabel, transitionSupportLabel } from '@/domain/terminology'
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
  /** Wording for the action: "selected" for PPO, "sampled" for the baseline. */
  verb: string
}

/** One strategy's sequence: the resistance matrix with the selected action ringed, and the ordered actions with transition support. */
export function SequenceCard({ title, badge, highlighted = false, initialProfile, steps, terminationReason, antibiotics, selectedStep, onSelectStep, verb }: SequenceCardProps) {
  const ordered = [...steps].sort((left, right) => left.treatmentStepAfter - right.treatmentStepAfter)
  const unsupported = ordered.filter((step) => !step.hasCandidateTransition).length
  const profiles = profilesFromSteps(initialProfile, steps)
  const shown = Math.min(selectedStep, profiles.length - 1)

  return (
    <Card className={cx(highlighted && styles['recommended'])} aria-label={title}>
      <CardHeader
        title={title}
        headingLevel="h2"
        description={ordered.length === 0 ? terminationLabel(terminationReason) : `${ordered.length} steps. ${terminationLabel(terminationReason)}.`}
        actions={badge ? <span className={styles['badge']}>{badge}</span> : undefined}
      />
      <div className="stack">
        <SequenceMatrix caption={`${title}: resistance by step`} entries={antibiotics} profiles={profiles} actions={actionsFromSteps(ordered)} selectedStep={shown} onSelectStep={onSelectStep} />
        {ordered.length > 0 ? (
          <ol className={cx(styles['sequence'], !highlighted && styles['muted'])} aria-label={`${title}, actions in order`}>
            {ordered.map((step) => (
              <li key={step.stepIndex} className={styles['sequenceItem']} aria-current={step.treatmentStepAfter === shown ? 'step' : undefined}>
                <span className={styles['stepNumber']} aria-label={`Step ${step.treatmentStepAfter}`}>
                  {step.treatmentStepAfter}
                </span>
                <span className={styles['name']}>{drugLabel(antibiotics, step.antibiotic)}</span>
                <StatusIndicator kind={step.hasCandidateTransition ? 'supported' : 'unsupported'} label={transitionSupportLabel(step.hasCandidateTransition)} />
                <span className="visually-hidden">{`${verb} at step ${step.treatmentStepAfter}`}</span>
              </li>
            ))}
          </ol>
        ) : null}
        {unsupported > 0 ? (
          <p className="muted" style={{ fontSize: 'var(--text-sm)' }}>
            {unsupported} of {ordered.length} steps had no supported transition data, so the simulator left the profile unchanged.
          </p>
        ) : null}
      </div>
    </Card>
  )
}
