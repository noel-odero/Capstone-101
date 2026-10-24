import { Navigate } from 'react-router'
import { ContentContainer } from '@/components/layout/ContentContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { RECENT_RUNS_PAGE_SIZE, useRecentRuns } from '@/hooks/useRecentRuns'
import { PAGE_TITLES } from '@/domain/terminology'

/** Open the latest three-strategy run, or configure a comparison with the current policies. */
export function SimulationIndex() {
  const recent = useRecentRuns(1, RECENT_RUNS_PAGE_SIZE)

  if (recent.isPending) {
    return (
      <ContentContainer>
        <PageHeader title={PAGE_TITLES.trajectory} />
        <LoadingState label="Opening your latest resistance trajectory" lines={2} />
      </ContentContainer>
    )
  }
  if (recent.isError) {
    return (
      <ContentContainer>
        <PageHeader title={PAGE_TITLES.trajectory} />
        <ErrorState error={recent.error} onRetry={() => void recent.refetch()} />
      </ContentContainer>
    )
  }

  const latest = recent.data.items.find(
    (run) =>
      run.kind === 'comparison' && run.strategies.some((strategy) => strategy.strategy === 'dqn'),
  )
  return <Navigate to={latest ? `/app/simulation/${latest.id}` : '/app/simulation/new'} replace />
}
