import { ButtonLink } from '@/components/ui/Button'
import { profileToCode } from '@/domain/profile'
import type { Comparison } from '@/domain/types'
import styles from './scientific.module.css'

export function ComparisonNotice({
  comparison,
}: {
  comparison: Pick<Comparison, 'ppo' | 'dqn' | 'sampleId'> & {
    provenance?: Comparison['provenance']
  }
}) {
  if (!comparison.ppo) return null
  const legacy = comparison.provenance?.actionMaskRule === 'susceptible_actions_only'
  if (comparison.dqn && !legacy) return null
  const query = comparison.sampleId
    ? `sample=${comparison.sampleId}`
    : `profile=${profileToCode(comparison.ppo.initialProfile)}`
  return (
    <aside className={styles.comparisonNotice} role="note">
      <span>
        {comparison.dqn
          ? 'Saved under earlier action rules. New evaluations require applicable transition evidence.'
          : 'This saved analysis predates DQN. Start a new analysis to include it.'}
      </span>
      <ButtonLink to={`/app/simulation/new?${query}`} variant="secondary" size="sm">
        {comparison.dqn ? 'Evaluate under current rules' : 'Analyze with DQN'}
      </ButtonLink>
    </aside>
  )
}
