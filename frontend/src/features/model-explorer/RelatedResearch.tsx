import { useState } from 'react'
import { Link } from 'react-router'
import { Pager } from '@/components/scientific/RunsTable'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { formatDateTime } from '@/domain/formatters'
import { strategyLabel } from '@/domain/terminology'
import { useSamples } from '@/features/samples/useSamples'
import { useAnalysisHistory } from '@/features/history/history-api'
import styles from './model-explorer.module.css'

export function RelatedResearch({ code }: { code: string }) {
  const [page, setPage] = useState(1)
  const samples = useSamples()
  const analyses = useAnalysisHistory(new URLSearchParams({ profile: code, page: String(page) }))
  const matching = samples.data?.filter((sample) => sample.resistanceProfile.join('') === code)
  return (
    <section className={styles.relatedResearch} aria-labelledby="research-heading">
      <div className={styles.sectionHeading}>
        <div>
          <span className={styles.eyebrow}>03 / YOUR RESEARCH</span>
          <h2 id="research-heading">Related to {code}</h2>
        </div>
        <Link to="/app/insights">Analysis Insights</Link>
      </div>
      <div className={styles.researchColumns}>
        <div>
          <h3>Recorded samples {matching ? <span>{matching.length}</span> : null}</h3>
          {samples.isPending ? <LoadingState label="Finding related samples" lines={2} /> : null}
          {samples.isError ? (
            <ErrorState error={samples.error} onRetry={() => void samples.refetch()} />
          ) : null}
          {matching?.length === 0 ? (
            <p className={styles.description}>No samples recorded with this state.</p>
          ) : null}
          <ul className={styles.researchList}>
            {matching?.map((sample) => (
              <li key={sample.id}>
                <Link to={`/app/simulation/new?sample=${sample.id}`}>{sample.label}</Link>
                <span>{formatDateTime(sample.addedAtUtc)}</span>
              </li>
            ))}
          </ul>
        </div>
        <div aria-busy={analyses.isFetching}>
          <h3>
            Saved analyses{' '}
            {analyses.data && !analyses.isPlaceholderData ? (
              <span>{analyses.data.totalCount}</span>
            ) : null}
          </h3>
          {analyses.isPending || analyses.isPlaceholderData ? (
            <LoadingState label="Finding related analyses" lines={2} />
          ) : null}
          {analyses.isError ? (
            <ErrorState error={analyses.error} onRetry={() => void analyses.refetch()} />
          ) : null}
          {analyses.data && !analyses.isPlaceholderData ? (
            <>
              {analyses.data.totalCount === 0 ? (
                <p className={styles.description}>No saved analyses started from this state.</p>
              ) : null}
              <ul className={styles.researchList}>
                {analyses.data.items.map((run) => (
                  <li key={run.id}>
                    <Link to={`/app/recommendations/${run.kind}/${run.id}`}>
                      {formatDateTime(run.createdAtUtc)}
                    </Link>
                    <span>
                      {run.strategies
                        .map((strategy) => strategyLabel(strategy.strategy))
                        .join(' · ')}
                    </span>
                  </li>
                ))}
              </ul>
              {analyses.data.totalCount > analyses.data.pageSize ? (
                <Pager data={analyses.data} onPage={setPage} />
              ) : null}
              {analyses.data.items.length >= 2 ? (
                <Link
                  className={styles.compareLink}
                  to={`/app/insights?ids=${analyses.data.items.map((run) => run.id).join(',')}`}
                >
                  Compare listed analyses
                </Link>
              ) : null}
            </>
          ) : null}
        </div>
      </div>
      <p className={styles.note}>
        Only your saved records are shown. Analyses match the starting binary code; recorded model
        versions and assumptions remain in their results.
      </p>
    </section>
  )
}
