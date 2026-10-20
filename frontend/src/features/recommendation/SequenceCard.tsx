import { SequenceMatrix } from '@/components/scientific/SequenceMatrix'
import { Card, CardHeader } from '@/components/ui/Card'
import { cx } from '@/components/ui/cx'
import type { AntibioticEntry } from '@/domain/antibiotics'
import { actionsFromSteps, profilesFromSteps } from '@/domain/trajectory'
import { terminationLabel } from '@/domain/terminology'
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

/** One strategy's sequence: the resistance matrix with the selected action ringed. The order of antibiotics is shown under Key metrics. */
export function SequenceCard({ title, badge, highlighted = false, initialProfile, steps, terminationReason, antibiotics, selectedStep, onSelectStep }: SequenceCardProps) {
  const ordered = [...steps].sort((left, right) => left.treatmentStepAfter - right.treatmentStepAfter)
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
      </div>
    </Card>
  )
}
