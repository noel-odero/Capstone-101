import type { ReactNode } from 'react'
import { cx } from './cx'
import styles from './ui.module.css'

export interface EmptyStateProps {
  title: string
  description: ReactNode
  icon?: ReactNode
  action?: ReactNode
}

export function EmptyState({ title, description, icon, action }: EmptyStateProps) {
  return (
    <div className={cx(styles['state'], styles['stateCentered'])}>
      {icon ? (
        <span className={styles['stateIcon']} aria-hidden="true">
          {icon}
        </span>
      ) : null}
      <h3>{title}</h3>
      <div className={styles['stateDescription']}>{description}</div>
      {action}
    </div>
  )
}
