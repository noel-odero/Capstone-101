import type { ReactNode } from 'react'
import { Tooltip } from './Tooltip'
import { cx } from './cx'
import { Card } from './Card'
import styles from './ui.module.css'

export interface MetricCardProps {
  label: string
  /** Formatted value, or null when the run did not provide one. A missing value is never rendered as zero. */
  value: string | null
  /** Unit or scale, so the number is never read in isolation. */
  caption?: string
  /** The server's definition of the metric, available from an info button. */
  definition?: string | undefined
  /** Extra context under the value, such as the other strategy's figure. */
  secondary?: ReactNode
}

export function MetricCard({ label, value, caption, definition, secondary }: MetricCardProps) {
  return (
    <Card as="div" className={styles['metric']}>
      <div className={styles['metricLabel']}>
        <span>{label}</span>
        {definition ? <Tooltip label={`Definition of ${label}`}>{definition}</Tooltip> : null}
      </div>
      <p className={cx(styles['metricValue'], value === null && styles['metricUnavailable'])}>
        {value ?? 'Not available'}
      </p>
      {caption ? <p className={styles['metricCaption']}>{caption}</p> : null}
      {secondary ? <div className={styles['metricSecondary']}>{secondary}</div> : null}
    </Card>
  )
}
