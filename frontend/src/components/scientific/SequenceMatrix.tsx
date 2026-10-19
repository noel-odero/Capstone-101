import { Check, X } from 'lucide-react'
import type { AntibioticEntry } from '@/domain/antibiotics'
import { RESISTANT } from '@/domain/profile'
import type { ResistanceProfile } from '@/domain/types'
import { cx } from '@/components/ui/cx'
import styles from './sequence-matrix.module.css'

export interface SequenceMatrixProps {
  /** Table caption, which also names the matrix for assistive technology. */
  caption: string
  entries: readonly AntibioticEntry[]
  /** The resistance profile at each state: index 0 is the initial state, index n follows the n-th action. */
  profiles: readonly ResistanceProfile[]
  /** `actions[n]` is the profile index of the antibiotic selected to reach state n (null at step 0 or when unknown). */
  actions?: ReadonlyArray<number | null>
  selectedStep?: number
  onSelectStep?: (step: number) => void
  /** A tag shown beside the caption, for example "Illustrative demo data". */
  tag?: string
}

/**
 * Antibiotics (rows) by treatment step (columns). Each dot is green with a check when susceptible and red with a cross when
 * resistant; a ringed dot marks the antibiotic selected at that step. The values are exactly the profiles supplied.
 */
export function SequenceMatrix({ caption, entries, profiles, actions, selectedStep, onSelectStep, tag }: SequenceMatrixProps) {
  return (
    <div>
      <div className={styles['wrap']}>
        <table className={styles['table']}>
          <caption>
            {caption} {tag ? <span className={styles['tag']}>{tag}</span> : null}
          </caption>
          <thead>
            <tr>
              <th scope="col" className={styles['rowHead']}>
                Antibiotic
              </th>
              {profiles.map((_, step) => (
                <th scope="col" key={step} className={cx(styles['stepHead'], selectedStep === step && styles['selectedColumn'], selectedStep === step && styles['selectedTop'])}>
                  {onSelectStep ? (
                    <button type="button" className={styles['stepButton']} aria-pressed={selectedStep === step} aria-label={`Step ${step}`} onClick={() => onSelectStep(step)}>
                      {step}
                    </button>
                  ) : (
                    step
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {entries.map((entry, row) => (
              <tr key={entry.actionId}>
                <th scope="row" className={styles['rowHead']}>
                  <span className={styles['drug']}>{entry.displayName}</span>
                </th>
                {profiles.map((profile, step) => {
                  const resistant = profile[entry.index] === RESISTANT
                  const selectedAction = actions?.[step] === entry.index
                  return (
                    <td
                      key={step}
                      className={cx(
                        styles['cell'],
                        selectedStep === step && styles['selectedColumn'],
                        selectedStep === step && row === entries.length - 1 && styles['selectedBottom'],
                      )}
                    >
                      <span className={cx(styles['dot'], resistant ? styles['resistant'] : styles['susceptible'], selectedAction && styles['action'])}>
                        {resistant ? <X size={11} strokeWidth={3} aria-hidden="true" /> : <Check size={11} strokeWidth={3} aria-hidden="true" />}
                        <span className="visually-hidden">
                          {resistant ? 'Resistant' : 'Susceptible'}
                          {selectedAction ? ', selected action' : ''}
                        </span>
                      </span>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className={styles['legend']} aria-hidden="true">
        <span>
          <span className={cx(styles['dot'], styles['susceptible'])}>
            <Check size={11} strokeWidth={3} />
          </span>
          Susceptible
        </span>
        <span>
          <span className={cx(styles['dot'], styles['resistant'])}>
            <X size={11} strokeWidth={3} />
          </span>
          Resistant
        </span>
        {actions ? (
          <span>
            <span className={cx(styles['dot'], styles['susceptible'], styles['action'])}>
              <Check size={11} strokeWidth={3} />
            </span>
            Selected action
          </span>
        ) : null}
      </div>
    </div>
  )
}
