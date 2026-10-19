import type { ReactNode } from 'react'
import styles from './layout.module.css'

export function ContentContainer({ children }: { children: ReactNode }) {
  return <div className={styles['container']}>{children}</div>
}
