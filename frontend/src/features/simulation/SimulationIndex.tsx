import { Navigate } from 'react-router'
import { ContentContainer } from '@/components/layout/ContentContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { RECENT_RUNS_PAGE_SIZE, useRecentRuns } from '@/hooks/useRecentRuns'

/** `/app/simulation`: opens your latest comparison, or the new-simulation form when you have none. */
export function SimulationIndex() {
  const recent = useRecentRuns(1, RECENT_RUNS_PAGE_SIZE)

  if (recent.isPending) {
    return (
      <ContentContainer>
        <PageHeader title="Simulation" />
        <LoadingState label="Opening your latest simulation" lines={2} />
      </ContentContainer>
    )
  }
  if (recent.isError) {
    return (
      <ContentContainer>
        <PageHeader title="Simulation" />
        <ErrorState error={recent.error} onRetry={() => void recent.refetch()} />
      </ContentContainer>
    )
  }

  const latest = recent.data.items.find((run) => run.kind === 'comparison')
  return <Navigate to={latest ? `/app/simulation/${latest.id}` : '/app/simulation/new'} replace />
}
