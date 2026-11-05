import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { FiTrash2 } from 'react-icons/fi'
import { Link } from 'react-router'
import { Button } from '@/components/ui/Button'
import { ErrorState } from '@/components/ui/ErrorState'
import { formatDateTime } from '@/domain/formatters'
import { profileToCode } from '@/domain/profile'
import { deleteSample, sampleKeys, type SavedSample } from './sample-api'
import styles from './samples.module.css'

export type SampleCategory = 'all' | 'pending' | 'run'
export function SampleList({
  samples,
  category = 'all',
}: {
  samples: readonly SavedSample[]
  category?: SampleCategory
}) {
  const [search, setSearch] = useState('')
  const [order, setOrder] = useState('newest')
  const [deleting, setDeleting] = useState<string | null>(null)
  const [notice, setNotice] = useState('')
  const client = useQueryClient()
  const remove = useMutation({
    mutationFn: deleteSample,
    retry: false,
    onSuccess: (_, id) => {
      setNotice('Sample deleted. Saved analyses remain in Analysis History.')
      setDeleting(null)
      client.setQueryData<SavedSample[]>(sampleKeys.all, (current) =>
        current?.filter((sample) => sample.id !== id),
      )
      void client.invalidateQueries({ queryKey: sampleKeys.all })
      void client.invalidateQueries({ queryKey: ['history-comparison'] })
      void client.invalidateQueries({ queryKey: ['comparison'] })
    },
  })
  const visible = samples
    .filter(
      (sample) =>
        (category === 'all' ||
          (category === 'run' ? sample.runs.length > 0 : sample.runs.length === 0)) &&
        sample.label.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()),
    )
    .sort((a, b) =>
      order === 'label'
        ? a.label.localeCompare(b.label)
        : order === 'oldest'
          ? a.addedAtUtc.localeCompare(b.addedAtUtc)
          : b.addedAtUtc.localeCompare(a.addedAtUtc),
    )
  return (
    <div>
      <div className={styles.filters}>
        <label>
          Find a sample
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search labels"
            type="search"
          />
        </label>
        <label>
          Sort by
          <select value={order} onChange={(event) => setOrder(event.target.value)}>
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="label">Label</option>
          </select>
        </label>
      </div>
      {notice ? (
        <p className={styles.notice} role="status">
          {notice}
        </p>
      ) : null}
      {visible.length ? (
        <div className={styles.sampleList}>
          {visible.map((sample) => (
            <article key={sample.id} className={styles.sampleRow}>
              <div className={styles.identity}>
                <h3>{sample.label}</h3>
                <span>Added {formatDateTime(sample.addedAtUtc)}</span>
              </div>
              <code>{profileToCode(sample.resistanceProfile)}</code>
              <span className={styles.status} data-run={sample.runs.length > 0}>
                {sample.runs.length
                  ? `Analyzed · ${sample.runs.length} ${sample.runs.length === 1 ? 'analysis' : 'analyses'}`
                  : 'Not analyzed'}
              </span>
              <div className={styles.rowActions}>
                <Link className={styles.action} to={`/app/simulation/new?sample=${sample.id}`}>
                  {sample.runs.length ? 'Analyze again' : 'New Analysis'}
                </Link>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Delete ${sample.label}`}
                  title="Delete sample"
                  disabled={remove.isPending}
                  onClick={() => {
                    setDeleting(sample.id)
                    setNotice('')
                    remove.reset()
                  }}
                >
                  <FiTrash2 aria-hidden="true" />
                </Button>
              </div>
              {deleting === sample.id ? (
                <div
                  className={styles.deleteConfirmation}
                  role="group"
                  aria-label={`Delete ${sample.label}?`}
                >
                  <p>Delete {sample.label}? Saved analyses will stay in Analysis History.</p>
                  <div className={styles.formActions}>
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={remove.isPending}
                      onClick={() => {
                        setDeleting(null)
                        remove.reset()
                      }}
                    >
                      Cancel
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      loading={remove.isPending}
                      onClick={() => remove.mutate(sample.id)}
                    >
                      Delete sample
                    </Button>
                  </div>
                  {remove.isError ? (
                    <ErrorState error={remove.error} title="Sample could not be deleted" />
                  ) : null}
                </div>
              ) : null}
              {sample.runs.length ? (
                <details className={styles.runHistory}>
                  <summary>Saved results</summary>
                  <ul>
                    {sample.runs.map((run) => (
                      <li key={run.id}>
                        <Link to={`/app/recommendations/comparison/${run.id}`}>
                          {formatDateTime(run.createdAtUtc)}
                        </Link>
                      </li>
                    ))}
                  </ul>
                </details>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <p className={styles.empty}>
          {search
            ? 'No labels match your search.'
            : category === 'pending'
              ? 'No samples are waiting to be analyzed.'
              : category === 'run'
                ? 'No samples have saved analyses yet.'
                : 'No samples recorded yet.'}
        </p>
      )}
    </div>
  )
}
