import { Bug } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import type { AntibioticEntry } from '@/domain/antibiotics'
import { countResistant, profileToCode, RESISTANT } from '@/domain/profile'
import type { ResistanceProfile } from '@/domain/types'
import styles from './profile.module.css'

/** The seven antibiotics with their state, and how many are resistant. Each state is a word and a dot, never colour alone. */
export function ProfileStrip({ profile, entries }: { profile: ResistanceProfile; entries: readonly AntibioticEntry[] }) {
  const resistant = countResistant(profile)
  return (
    <div className={styles['strip']}>
      <Card className={styles['profileCard']} aria-labelledby="profile-title">
        <div className={styles['identity']}>
          <span className={styles['profileIcon']} aria-hidden="true">
            <Bug size={26} />
          </span>
          <div>
            <h2 id="profile-title" className={styles['profileTitle']}>
              Resistance Profile
            </h2>
            <p className={styles['code']} aria-label={`Profile ${profileToCode(profile)}`}>
              {profileToCode(profile).split('').join(' ')}
            </p>
            <p className="muted" style={{ fontSize: 'var(--text-xs)' }}>
              ({entries.length} drugs)
            </p>
          </div>
        </div>
        <ul className={styles['drugs']} aria-label="Resistance of each antibiotic">
          {entries.map((entry) => {
            const isResistant = profile[entry.index] === RESISTANT
            return (
              <li key={entry.actionId} aria-label={`${entry.displayName}: ${isResistant ? 'resistant' : 'susceptible'}`}>
                <span className={styles['abbr']}>{entry.abbreviation ?? entry.displayName}</span>
                <span className={styles['state']}>
                  <span className={isResistant ? styles['dotResistant'] : styles['dotSusceptible']} aria-hidden="true" />
                  {isResistant ? 'R' : 'S'}
                </span>
              </li>
            )
          })}
        </ul>
      </Card>
      <Card className={styles['levelCard']} aria-label="Resistance level">
        <p className={styles['levelLabel']}>Resistance Level</p>
        <p className={styles['level']}>
          {resistant}
          <span> / {entries.length}</span>
        </p>
        <p className="muted" style={{ fontSize: 'var(--text-xs)' }}>
          Drugs resistant
        </p>
      </Card>
    </div>
  )
}
