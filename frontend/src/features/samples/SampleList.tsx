import { useState } from 'react'
import { Link } from 'react-router'
import { formatDateTime } from '@/domain/formatters'
import { profileToCode } from '@/domain/profile'
import type { SavedSample } from './sample-api'
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
              <Link className={styles.action} to={`/app/simulation/new?sample=${sample.id}`}>
                {sample.runs.length ? 'Analyze again' : 'New Analysis'}
              </Link>
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
