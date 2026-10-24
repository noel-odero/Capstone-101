import type { ResistanceProfile } from '@/domain/types'
import styles from './history.module.css'

export function ProfileIndicators({
  profile,
  order,
}: {
  profile: ResistanceProfile
  order?: readonly string[] | undefined
}) {
  return (
    <span className={styles.profile}>
      <code>{profile.join('')}</code>
      <span className={styles.bits} aria-label="Initial resistance states">
        {profile.map((state, index) => {
          const label = `${order?.[index] ?? `Position ${index + 1}`}: ${state ? 'resistant' : 'susceptible'}`
          return (
            <span
              key={index}
              className={state ? styles.resistant : styles.susceptible}
              title={label}
              aria-label={label}
            >
              {state ? 'R' : 'S'}
            </span>
          )
        })}
      </span>
    </span>
  )
}
