import { ContentContainer } from '@/components/layout/ContentContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { ButtonLink } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { RECENT_RUNS_PAGE_SIZE, useRecentRuns } from '@/hooks/useRecentRuns'
import { Navigate } from 'react-router'
import { PAGE_TITLES } from '@/domain/terminology'

/** `/app/recommendations`: opens the sequences of your latest run, or invites you to run one. */
export function RecommendationsIndex() {
  const recent = useRecentRuns(1, RECENT_RUNS_PAGE_SIZE)

  if (recent.isPending) {
    return (
      <ContentContainer>
        <PageHeader title={PAGE_TITLES.results} />
        <LoadingState label="Opening your latest run" lines={2} />
      </ContentContainer>
    )
  }
  if (recent.isError) {
    return (
      <ContentContainer>
        <PageHeader title={PAGE_TITLES.results} />
        <ErrorState error={recent.error} onRetry={() => void recent.refetch()} />
      </ContentContainer>
    )
  }

  const comparison =
    recent.data.items.find(
      (run) =>
        run.kind === 'comparison' && run.strategies.some((strategy) => strategy.strategy === 'dqn'),
    ) ?? recent.data.items.find((run) => run.kind === 'comparison')
  if (comparison) {
    return <Navigate to={`/app/recommendations/comparison/${comparison.id}`} replace />
  }
  const simulation = recent.data.items.find((run) =>
    run.strategies.some((strategy) => strategy.strategy === 'ppo'),
  )
  if (simulation) {
    return <Navigate to={`/app/recommendations/simulation/${simulation.id}`} replace />
  }
  return (
    <ContentContainer>
      <PageHeader
        title={PAGE_TITLES.results}
        subtitle="Strategy sequences and model-derived outcomes from your analyses."
      />
      <EmptyState
        title="No sequences yet"
        description="Compare PPO, DQN and the baseline to review their sequences and outcomes."
        action={
          <ButtonLink to="/app/simulation/new" variant="dark">
            New Analysis
          </ButtonLink>
        }
      />
    </ContentContainer>
  )
}
