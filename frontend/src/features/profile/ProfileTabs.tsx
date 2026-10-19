import { NavLink } from 'react-router'
import styles from './profile.module.css'

/** Switches between the profile and the experiment history; both belong to the E. coli Profile section. */
export function ProfileTabs() {
  return (
    <nav className={styles['tabs']} aria-label="Profile sections">
      <NavLink to="/app/profile" end className={styles['tab']}>
        Overview
      </NavLink>
      <NavLink to="/app/history" className={styles['tab']}>
        Treatment history
      </NavLink>
    </nav>
  )
}
