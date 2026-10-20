import { NavLink } from 'react-router'
import { cx } from '@/components/ui/cx'
import { recommendationPath } from '@/domain/runs'
import { useLatestPpoRun } from '@/hooks/useLatestPpoRun'
import styles from './profile.module.css'

/** The sections of the E. coli Profile: how resistance evolves, the recommended sequence, and the history of past experiments. */
export function ProfileTabs() {
  const latest = useLatestPpoRun()
  const recommendations = latest.run ? recommendationPath(latest.run) : null
  return (
    <nav className={styles['tabs']} aria-label="Profile sections">
      <NavLink to="/app/profile" end className={styles['tab']}>
        Resistance evolution
      </NavLink>
      {recommendations ? (
        <NavLink to={recommendations} className={styles['tab']}>
          Treatment recommendations
        </NavLink>
      ) : (
        <span className={cx(styles['tab'], styles['tabOff'])} aria-disabled="true">
          Treatment recommendations
        </span>
      )}
      <NavLink to="/app/history" className={styles['tab']}>
        Treatment history
      </NavLink>
    </nav>
  )
}
