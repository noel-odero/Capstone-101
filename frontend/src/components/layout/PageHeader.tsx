import { useEffect, type ReactNode } from 'react'
import { APP_NAME } from '@/domain/terminology'
import styles from './layout.module.css'

export interface PageHeaderProps {
  title: string
  subtitle?: ReactNode
  eyebrow?: string
  /** The page's primary action, shown at the end of the header. */
  action?: ReactNode
}

export function PageHeader({ title, subtitle, eyebrow, action }: PageHeaderProps) {
  useEffect(() => {
    document.title = title === APP_NAME ? APP_NAME : `${title} \u00b7 ${APP_NAME}`
  }, [title])

  return (
    <header className={styles['pageHeader']}>
      <div className={styles['pageHeading']}>
        {eyebrow ? <span className={styles['eyebrow']}>{eyebrow}</span> : null}
        <h1 className={styles['pageTitle']}>{title}</h1>
        {subtitle ? <p className={styles['pageSubtitle']}>{subtitle}</p> : null}
      </div>
      {action}
    </header>
  )
}
