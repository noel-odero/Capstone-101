import { FiCheckCircle as CircleCheck, FiXCircle as CircleX } from 'react-icons/fi'
import type { AntibioticEntry } from '@/domain/antibiotics'
import { RESISTANT } from '@/domain/profile'
import type { ResistanceProfile } from '@/domain/types'
import { cx } from '@/components/ui/cx'
import styles from './scientific.module.css'

export interface ResistanceProfileGridProps {
  entries: readonly AntibioticEntry[]
  profile: ResistanceProfile
  /** When given, every antibiotic is a toggle button; without it the grid is a read-only list. */
  onToggle?: (index: number) => void
  compact?: boolean
  /** Positions that changed relative to another profile; shown with a "Changed" label as well as an outline. */
  changed?: ReadonlySet<number>
  label: string
}

/** Seven antibiotics in profile order. State is always written out ("Susceptible"/"Resistant"), never colour alone. */
export function ResistanceProfileGrid({
  entries,
  profile,
  onToggle,
  compact = false,
  changed,
  label,
}: ResistanceProfileGridProps) {
  return (
    <ul className={cx(styles['tileGrid'], compact && styles['tileGridCompact'])} aria-label={label}>
      {entries.map((entry) => {
        const resistant = profile[entry.index] === RESISTANT
        const stateLabel = resistant ? 'Resistant' : 'Susceptible'
        const isChanged = changed?.has(entry.index) ?? false
        const className = cx(
          styles['tile'],
          resistant ? styles['tileResistant'] : styles['tileSusceptible'],
          isChanged && styles['tileChanged'],
        )
        const content = (
          <>
            <span className={styles['tileCode']}>{entry.abbreviation ?? entry.displayName}</span>
            <span className={styles['tileName']}>{entry.displayName}</span>
            <span className={styles['tileNote']}>
              {resistant ? (
                <CircleX size={12} aria-hidden="true" />
              ) : (
                <CircleCheck size={12} aria-hidden="true" />
              )}{' '}
              {stateLabel}
              {isChanged ? ' \u00b7 Changed' : ''}
            </span>
          </>
        )
        return (
          <li key={entry.actionId}>
            {onToggle ? (
              <button
                type="button"
                className={className}
                aria-pressed={resistant}
                aria-label={`${entry.displayName}: ${stateLabel.toLowerCase()}. Press to mark ${resistant ? 'susceptible' : 'resistant'}.`}
                onClick={() => onToggle(entry.index)}
              >
                {content}
              </button>
            ) : (
              <div className={className}>{content}</div>
            )}
          </li>
        )
      })}
    </ul>
  )
}
