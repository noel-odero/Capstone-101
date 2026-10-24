import { ButtonLink } from '@/components/ui/Button'
import { profileToCode } from '@/domain/profile'
import type { Comparison } from '@/domain/types'
import styles from './scientific.module.css'

export function ComparisonNotice({
  comparison,
}: {
  comparison: Pick<Comparison, 'ppo' | 'dqn' | 'sampleId'>
}) {
  if (!comparison.ppo || comparison.dqn) return null
  const query = comparison.sampleId
    ? `sample=${comparison.sampleId}`
    : `profile=${profileToCode(comparison.ppo.initialProfile)}`
  return (
    <aside className={styles.comparisonNotice} role="note">
      <span>This saved analysis predates DQN. Start a new analysis to include it.</span>
      <ButtonLink to={`/app/simulation/new?${query}`} variant="secondary" size="sm">
        Analyze with DQN
      </ButtonLink>
    </aside>
  )
}
