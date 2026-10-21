import { FiGitBranch as Route, FiGitMerge as Scale, FiShield as ShieldCheck } from 'react-icons/fi'
import type { IconType } from 'react-icons'
import { Card, CardHeader } from '@/components/ui/Card'
import type { AntibioticEntry } from '@/domain/antibiotics'
import { buildInsights, type Insight } from '@/domain/profileInsights'
import type { ProfileRun } from './useProfileRun'
import styles from './profile.module.css'

const ICONS: Readonly<Record<Insight['id'], IconType>> = {
  current: ShieldCheck,
  'first-step': Route,
  comparison: Scale,
}

/** Three plain statements computed from the run. Nothing here is a prediction. */
export function KeyInsights({
  run,
  entries,
}: {
  run: ProfileRun
  entries: readonly AntibioticEntry[]
}) {
  const insights = buildInsights(run.ppo, run.baseline, entries)
  return (
    <Card aria-labelledby="insights-title">
      <CardHeader titleId="insights-title" title="Key insights" />
      <ul className={styles['insights']}>
        {insights.map((insight) => {
          const Icon = ICONS[insight.id]
          return (
            <li key={insight.id}>
              <span
                className={`${styles['insightIcon']} ${styles[`tone-${insight.tone}`]}`}
                aria-hidden="true"
              >
                <Icon size={18} />
              </span>
              <div>
                <h3>{insight.title}</h3>
                <p>{insight.text}</p>
              </div>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}
