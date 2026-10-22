import { ContentContainer } from '@/components/layout/ContentContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { ButtonLink } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { RECENT_RUNS_PAGE_SIZE, useRecentRuns } from '@/hooks/useRecentRuns'
import { Navigate } from 'react-router'

/** `/app/recommendations`: opens the sequences of your latest run, or invites you to run one. */
export function RecommendationsIndex() {
  const recent = useRecentRuns(1, RECENT_RUNS_PAGE_SIZE)

  if (recent.isPending) {
    return (
      <ContentContainer>
        <PageHeader title="Recommendations" />
        <LoadingState label="Opening your latest run" lines={2} />
      </ContentContainer>
    )
  }
  if (recent.isError) {
    return (
      <ContentContainer>
        <PageHeader title="Recommendations" />
        <ErrorState error={recent.error} onRetry={() => void recent.refetch()} />
      </ContentContainer>
    )
  }

  const comparison = recent.data.items.find((run) => run.kind === 'comparison')
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
      <PageHeader title="Recommendations" subtitle="The PPO-selected sequence from your runs." />
      <EmptyState
        title="No sequences yet"
        description="Run a simulation and its PPO-selected sequence will appear here."
        action={
          <ButtonLink to="/app/simulation/new" variant="dark">
            Run New Simulation
          </ButtonLink>
        }
      />
    </ContentContainer>
  )
}
