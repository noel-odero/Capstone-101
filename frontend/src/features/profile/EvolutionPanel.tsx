import { FiInfo as Info } from 'react-icons/fi'
import { useState } from 'react'
import { SequenceMatrix } from '@/components/scientific/SequenceMatrix'
import type { AntibioticEntry } from '@/domain/antibiotics'
import { drugLabel } from '@/domain/antibiotics'
import { actionsFromSteps, profilesFromSteps } from '@/domain/trajectory'
import { terminationLabel } from '@/domain/terminology'
import type { ProfileRun } from './useProfileRun'
import styles from './profile.module.css'

/** How resistance changes step by step along the PPO-selected sequence, and the sequence itself as numbered cards. */
export function EvolutionPanel({
  run,
  entries,
}: {
  run: ProfileRun
  entries: readonly AntibioticEntry[]
}) {
  const [selected, setSelected] = useState(1)
  const { ppo } = run
  const ordered = [...ppo.steps].sort(
    (left, right) => left.treatmentStepAfter - right.treatmentStepAfter,
  )
  const profiles = profilesFromSteps(ppo.initialProfile, ppo.steps)
  const shown = Math.min(selected, profiles.length - 1)

  return (
    <div className={styles['evolution']}>
      <div>
        <h3 className={styles['panelTitle']}>Resistance by step</h3>
        <p className="muted" style={{ fontSize: 'var(--text-sm)' }}>
          Each dot is the state of one antibiotic after each step of the PPO-selected sequence.
        </p>
      </div>
      <SequenceMatrix
        caption="Each antibiotic after each step"
        entries={entries}
        profiles={profiles}
        actions={actionsFromSteps(ordered)}
        selectedStep={shown}
        onSelectStep={setSelected}
      />

      <div>
        <h3 className={styles['panelTitle']}>Model recommendations</h3>
        <p className="muted" style={{ fontSize: 'var(--text-sm)' }}>
          {ordered.length === 0
            ? terminationLabel(ppo.terminationReason)
            : `The antibiotics PPO chose, in order (${ordered.length} steps).`}
        </p>
      </div>
      {ordered.length > 0 ? (
        <ol className={styles['steps']} aria-label="PPO-selected antibiotics in order">
          {ordered.map((step) => {
            return (
              <li
                key={step.stepIndex}
                className={styles['stepCard']}
                aria-current={step.treatmentStepAfter === shown ? 'step' : undefined}
              >
                <span className={styles['stepLabel']}>Step {step.treatmentStepAfter}</span>
                <span className={styles['drugChip']}>{drugLabel(entries, step.antibiotic)}</span>
              </li>
            )
          })}
        </ol>
      ) : null}
      <p className={styles['note']}>
        <Info size={16} aria-hidden="true" /> This sequence is the model&apos;s choice in a
        simplified simulation, not treatment advice.
      </p>
    </div>
  )
}
