import type { ReactNode } from 'react'
import styles from './ui.module.css'

export interface DisclosureProps {
  summary: string
  children: ReactNode
  defaultOpen?: boolean
}

/** Native details/summary: keyboard and screen-reader behaviour comes from the browser. */
export function Disclosure({ summary, children, defaultOpen = false }: DisclosureProps) {
  return (
    <details className={styles['disclosure']} open={defaultOpen}>
      <summary>{summary}</summary>
      <div className={styles['disclosureBody']}>{children}</div>
    </details>
  )
}
