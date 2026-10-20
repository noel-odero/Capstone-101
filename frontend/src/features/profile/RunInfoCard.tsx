import { Bug } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { formatDateTime, shortId } from '@/domain/formatters'
import { PROJECT_LOCATION } from '@/domain/terminology'
import type { ProfileRun } from './useProfileRun'
import styles from './profile.module.css'

/** Which stored run the page describes. Only facts the run record holds, plus the project location. */
export function RunInfoCard({ run }: { run: ProfileRun }) {
  return (
    <Card className={styles['runInfo']} aria-label="Run details">
      <span className={styles['runIcon']} aria-hidden="true">
        <Bug size={22} />
      </span>
      <dl className={styles['runFacts']}>
        <div>
          <dt>Run</dt>
          <dd className={styles['mono']}>{shortId(run.summary.id)}</dd>
        </div>
        <div>
          <dt>Date</dt>
          <dd>{formatDateTime(run.summary.createdAtUtc)}</dd>
        </div>
        <div>
          <dt>Model</dt>
          <dd>{run.provenance.modelId}</dd>
        </div>
        <div>
          <dt>Location</dt>
          <dd>{PROJECT_LOCATION}</dd>
        </div>
      </dl>
    </Card>
  )
}
