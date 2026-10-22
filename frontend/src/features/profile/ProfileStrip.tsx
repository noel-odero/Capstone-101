import { Card } from '@/components/ui/Card'
import type { AntibioticEntry } from '@/domain/antibiotics'
import { countResistant, profileToCode, RESISTANT } from '@/domain/profile'
import type { ResistanceProfile } from '@/domain/types'
import styles from './profile.module.css'

/** The seven antibiotics with their state, and how many are resistant. Each state is a word and a dot, never colour alone. */
export function ProfileStrip({
  profile,
  entries,
}: {
  profile: ResistanceProfile
  entries: readonly AntibioticEntry[]
}) {
  const resistant = countResistant(profile)
  return (
    <div className={styles['strip']}>
      <Card className={styles['profileCard']} aria-labelledby="profile-title">
        <div className={styles['stripHeading']}>
          <h2 id="profile-title" className={styles['profileTitle']}>
            Current Resistance Profile
          </h2>
          <p className="visually-hidden" aria-label={`Profile ${profileToCode(profile)}`}>
            {profileToCode(profile).split('').join(' ')}
          </p>
          <p className={styles['stripCount']} aria-label="Resistance level">
            {resistant} / {entries.length} resistant
          </p>
        </div>
        <ul className={styles['drugs']} aria-label="Resistance of each antibiotic">
          {entries.map((entry) => {
            const isResistant = profile[entry.index] === RESISTANT
            return (
              <li
                key={entry.actionId}
                aria-label={`${entry.displayName}: ${isResistant ? 'resistant' : 'susceptible'}`}
              >
                <span className={styles['abbr']}>{entry.abbreviation ?? entry.displayName}</span>
                <span className={styles['state']}>
                  <span
                    className={isResistant ? styles['dotResistant'] : styles['dotSusceptible']}
                    aria-hidden="true"
                  />
                  {isResistant ? 'R' : 'S'}
                </span>
              </li>
            )
          })}
        </ul>
      </Card>
    </div>
  )
}
