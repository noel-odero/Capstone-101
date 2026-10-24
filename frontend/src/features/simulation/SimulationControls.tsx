import { ButtonLink } from '@/components/ui/Button'
import { countResistant, countSusceptible, profileToCode } from '@/domain/profile'
import type { ResistanceProfile } from '@/domain/types'
import styles from './simulation.module.css'

/** Stored starting conditions; configuration belongs to the simulation setup page. */
export function SimulationControls({
  initialProfile,
  horizon,
}: {
  initialProfile: ResistanceProfile
  horizon: number
}) {
  return (
    <section className={styles.initialConditions} aria-label="Initial analysis conditions">
      <dl className={styles.initialSummary}>
        <div>
          <dt>Initial profile</dt>
          <dd>
            <code>{profileToCode(initialProfile)}</code>
            <span>
              {countResistant(initialProfile)} resistant · {countSusceptible(initialProfile)}{' '}
              susceptible
            </span>
          </dd>
        </div>
        <div>
          <dt>Horizon</dt>
          <dd>{horizon} steps</dd>
        </div>
      </dl>
      <ButtonLink
        to={`/app/simulation/new?profile=${profileToCode(initialProfile)}`}
        variant="secondary"
        size="sm"
      >
        New Analysis
      </ButtonLink>
    </section>
  )
}
