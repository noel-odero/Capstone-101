import { cx } from '@/components/ui/cx'
import type { AntibioticEntry } from '@/domain/antibiotics'
import { drugLabel } from '@/domain/antibiotics'
import type { StepTrace } from '@/domain/types'
import styles from './recommendation.module.css'

export interface SequenceOrderRow {
  label: string
  steps: readonly StepTrace[]
  /** The PPO-selected sequence gets the accent colour. */
  highlighted?: boolean
}

export interface SequenceOrderProps {
  rows: readonly SequenceOrderRow[]
  antibiotics: readonly AntibioticEntry[]
  selectedStep: number
}

/** The antibiotics of each sequence in the order they were given, as compact chips that wrap instead of one row per step. */
export function SequenceOrder({ rows, antibiotics, selectedStep }: SequenceOrderProps) {
  return (
    <div className={styles['order']}>
      <h3>Order of antibiotics</h3>
      {rows.map((row) => {
        const ordered = [...row.steps].sort((left, right) => left.treatmentStepAfter - right.treatmentStepAfter)
        return (
          <div key={row.label} className={cx(styles['orderRow'], row.highlighted && styles['primary'])}>
            <span className={styles['orderLabel']}>{row.label}</span>
            {ordered.length === 0 ? (
              <span className="muted">No steps</span>
            ) : (
              <ol className={styles['orderList']} aria-label={`${row.label}, antibiotics in order`}>
                {ordered.map((step) => (
                  <li key={step.stepIndex} className={styles['orderChip']} aria-current={step.treatmentStepAfter === selectedStep ? 'step' : undefined}>
                    <span className={styles['orderNumber']} aria-label={`Step ${step.treatmentStepAfter}`}>
                      {step.treatmentStepAfter}
                    </span>
                    {drugLabel(antibiotics, step.antibiotic)}
                  </li>
                ))}
              </ol>
            )}
          </div>
        )
      })}
    </div>
  )
}
