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
import { SampleList } from '@/features/samples/SampleList'
import { useSamples } from '@/features/samples/useSamples'
import { PAGE_TITLES } from '@/domain/terminology'
import sampleStyles from '@/features/samples/samples.module.css'

export function HistoryPage() {
  const [params, setParams] = useSearchParams()
  const requested = Number(params.get('page'))
  const page = Number.isInteger(requested) && requested >= 1 ? requested : 1
  const runs = useRecentRuns(page, RECENT_RUNS_PAGE_SIZE)
  const samples = useSamples()
  const requestedCategory = params.get('category')
  const category =
    requestedCategory === 'pending' || requestedCategory === 'run' ? requestedCategory : 'runs'
  return (
    <ContentContainer>
      <PageHeader
        title={PAGE_TITLES.history}
        subtitle="Revisit saved evaluations and compare initial resistance profiles."
        action={
          <ButtonLink to="/app/simulation/new" variant="dark">
            New Analysis
          </ButtonLink>
        }
      />
      <div className={sampleStyles.categories} role="group" aria-label="History categories">
        {[
          ['runs', 'All analyses'],
          ['pending', 'Samples not analyzed'],
          ['run', 'Samples analyzed'],
        ].map(([key, label]) => (
          <button
            key={key}
            type="button"
            aria-pressed={category === key}
            onClick={() => setParams({ category: key ?? 'runs' })}
          >
            {label}
          </button>
        ))}
        <ButtonLink to="/app/samples" variant="secondary" size="sm">
          Record samples
        </ButtonLink>
      </div>
      {category !== 'runs' ? (
        <>
          {samples.isPending ? <LoadingState label="Loading samples" lines={3} /> : null}
          {samples.isError ? (
            <ErrorState error={samples.error} onRetry={() => void samples.refetch()} />
          ) : null}
          {samples.data ? (
            <SampleList samples={samples.data} category={category === 'run' ? 'run' : 'pending'} />
          ) : null}
        </>
      ) : (
        <>
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
              title="No analyses yet"
              description="Your saved analyses will be listed here."
              action={
                <ButtonLink to="/app/simulation/new" variant="dark">
                  New Analysis
                </ButtonLink>
              }
            />
          ) : null}
          {runs.data && runs.data.totalCount > 0 ? (
            <Card as="div" flush>
              {runs.data.items.length === 0 ? (
                <p style={{ padding: 'var(--space-4)' }}>No analyses on this page.</p>
              ) : (
                <RunsTable
                  runs={runs.data.items}
                  caption="Your analyses, newest first"
                  sampleLabels={
                    new Map(
                      samples.data?.flatMap((sample) =>
                        sample.runs.map((run) => [run.id, sample.label] as const),
                      ) ?? [],
                    )
                  }
                />
              )}
              <Pager data={runs.data} onPage={(next) => setParams({ page: String(next) })} />
            </Card>
          ) : null}
        </>
      )}
    </ContentContainer>
  )
}
