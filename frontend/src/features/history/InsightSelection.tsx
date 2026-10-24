import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { RunsTable, Pager } from '@/components/scientific/RunsTable'
import { HistoryFilters } from './HistoryFilters'
import { SELECTION_LIMIT, useAnalysisHistory } from './history-api'
import styles from './insights.module.css'

export function InsightSelection({
  ids,
  onApply,
  onCancel,
}: {
  ids: string[]
  onApply: (ids: string[]) => void
  onCancel: () => void
}) {
  const [params, setParams] = useState(new URLSearchParams())
  const [selected, setSelected] = useState(ids)
  const [error, setError] = useState('')
  const history = useAnalysisHistory(params)
  return (
    <section className={styles.panel} aria-label="Choose evidence for insights">
      <div className={styles.panelHeading}>
        <div>
          <h2>Choose analyses</h2>
          <p>Build a selection across pages. Your archive stays unchanged.</p>
        </div>
        <Button size="sm" variant="ghost" onClick={onCancel}>
          Close selection
        </Button>
      </div>
      <div className={styles.selectionFilters}>
        <HistoryFilters
          key={params.toString().replace(/page=\d+&?/, '')}
          params={params}
          onApply={(values) =>
            setParams(
              new URLSearchParams(Object.entries(values).filter(([, value]) => value !== '')),
            )
          }
        />
      </div>
      <div className={styles.selectionToolbar}>
        <span aria-live="polite">
          {selected.length} / {SELECTION_LIMIT} analyses selected
        </span>
        <span className="row">
          <Button size="sm" variant="ghost" onClick={() => setSelected([])}>
            Clear selection
          </Button>
          <Button
            size="sm"
            variant="secondary"
            disabled={!history.data || history.isPlaceholderData}
            onClick={() => {
              setSelected(history.data?.items.slice(0, SELECTION_LIMIT).map((run) => run.id) ?? [])
              setError('')
            }}
          >
            Use this page
          </Button>
          <Button
            disabled={selected.length < 2 || selected.length > SELECTION_LIMIT}
            onClick={() => onApply(selected)}
          >
            Update insights
          </Button>
        </span>
      </div>
      {error ? (
        <p role="alert" className={styles.notice}>
          {error}
        </p>
      ) : null}
      {history.isPending ? <LoadingState label="Loading saved analyses" lines={4} /> : null}
      {history.isError ? (
        <ErrorState error={history.error} onRetry={() => void history.refetch()} />
      ) : null}
      {history.data ? (
        <>
          {history.data.items.length ? (
            <RunsTable
              runs={history.data.items}
              caption="Choose saved evidence"
              selection={{
                ids: selected,
                disabled: history.isPlaceholderData,
                onToggle: (next) => {
                  if (next.length > SELECTION_LIMIT) {
                    setError(`Choose up to ${SELECTION_LIMIT} analyses at a time.`)
                    return
                  }
                  setSelected(next)
                  setError('')
                },
              }}
            />
          ) : (
            <p className={styles.notice}>No analyses match these filters.</p>
          )}
          <Pager
            data={history.data}
            onPage={(page) =>
              setParams((previous) => {
                const next = new URLSearchParams(previous)
                next.set('page', String(page))
                return next
              })
            }
          />
        </>
      ) : null}
    </section>
  )
}
