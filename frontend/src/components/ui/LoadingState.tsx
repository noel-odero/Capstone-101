import styles from './ui.module.css'

export interface LoadingStateProps {
  label?: string
  /** Number of placeholder lines; keeps the layout from jumping when content arrives. */
  lines?: number
  block?: boolean
}

/** Announces progress without implying a percentage: the work has no measurable progress. */
export function LoadingState({ label = 'Loading', lines = 3, block = false }: LoadingStateProps) {
  return (
    <div className={styles['loading']} role="status" aria-live="polite">
      <span className={styles['loadingLabel']}>
        <span className={styles['spinner']} aria-hidden="true" />
        {label}
      </span>
      {block ? (
        <div className={`${styles['skeleton']} ${styles['skeletonBlock']}`} aria-hidden="true" />
      ) : null}
      {Array.from({ length: lines }, (_, index) => (
        <div
          key={index}
          className={styles['skeleton']}
          style={{ width: `${100 - index * 12}%` }}
          aria-hidden="true"
        />
      ))}
    </div>
  )
}
