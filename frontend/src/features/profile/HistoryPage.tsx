import { useSearchParams } from 'react-router'
import { ContentContainer } from '@/components/layout/ContentContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { Pager, RunsTable } from '@/components/scientific/RunsTable'
import { ButtonLink } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { RECENT_RUNS_PAGE_SIZE, useRecentRuns } from '@/hooks/useRecentRuns'
import { ProfileTabs } from './ProfileTabs'

/** Your stored experiments, newest first. Each row opens its simulation or PPO sequence. */
export function HistoryPage() {
  const [params, setParams] = useSearchParams()
  const requested = Number(params.get('page'))
  const page = Number.isInteger(requested) && requested >= 1 ? requested : 1
  const runs = useRecentRuns(page, RECENT_RUNS_PAGE_SIZE)

  return (
    <ContentContainer>
      <PageHeader
        title="Experiment History"
        subtitle="Reopen your saved simulations and strategy comparisons."
        action={
          <ButtonLink to="/app/simulation/new" variant="dark">
            New Experiment
          </ButtonLink>
        }
      />
      <ProfileTabs />
      {runs.isPending ? <LoadingState label="Loading your history" lines={4} /> : null}
      {runs.isError ? (
        <ErrorState
          error={runs.error}
          title="Your history could not be loaded"
          onRetry={() => void runs.refetch()}
        />
      ) : null}
      {runs.data && runs.data.totalCount === 0 ? (
        <EmptyState
          title="No simulations yet"
          description="Your simulations will be listed here."
          action={
            <ButtonLink to="/app/simulation/new" variant="dark">
              Run Simulation
            </ButtonLink>
          }
        />
      ) : null}
      {runs.data && runs.data.totalCount > 0 ? (
        <Card as="div" flush>
          {runs.data.items.length === 0 ? (
            <p style={{ padding: 'var(--space-4)' }}>No runs on this page.</p>
          ) : (
            <RunsTable runs={runs.data.items} caption="Your simulations, newest first" />
          )}
          <Pager data={runs.data} onPage={(next) => setParams({ page: String(next) })} />
        </Card>
      ) : null}
    </ContentContainer>
  )
}
