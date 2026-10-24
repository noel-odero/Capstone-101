import type { FormEvent } from 'react'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { formatDateTime } from '@/domain/formatters'
import { useAnalysisCollections, useSaveCollection, type AnalysisCollection } from './history-api'
import styles from './insights.module.css'

export function InsightCollections({
  ids,
  onOpen,
  onChoose,
}: {
  ids: string[]
  onOpen: (collection: AnalysisCollection) => void
  onChoose: () => void
}) {
  const collections = useAnalysisCollections()
  const save = useSaveCollection()
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const values = new FormData(form)
    save.mutate(
      {
        name: String(values.get('name') ?? '').trim(),
        question: String(values.get('question') ?? '').trim(),
        analysisIds: ids,
      },
      {
        onSuccess: () => form.reset(),
      },
    )
  }
  return (
    <div className={styles.collectionGrid}>
      <section className={styles.panel} aria-labelledby="collections-heading">
        <div className={styles.panelHeading}>
          <div>
            <h2 id="collections-heading">Research collections</h2>
            <p>Keep the records behind a question together.</p>
          </div>
        </div>
        {collections.isPending ? <LoadingState label="Loading collections" lines={2} /> : null}
        {collections.isError ? (
          <ErrorState error={collections.error} onRetry={() => void collections.refetch()} />
        ) : null}
        {collections.data?.length === 0 ? (
          <EmptyState
            title="Your first research question starts here"
            description="Save the current selection with a name and a question to investigate."
          />
        ) : null}
        <div className={styles.collectionList}>
          {collections.data?.map((collection) => (
            <article key={collection.id}>
              <div>
                <h3>{collection.name}</h3>
                {collection.question ? <p>{collection.question}</p> : null}
                <small>
                  {collection.analysisIds.length} analyses ·{' '}
                  {formatDateTime(collection.createdAtUtc)}
                </small>
              </div>
              <Button size="sm" variant="secondary" onClick={() => onOpen(collection)}>
                Open collection
              </Button>
            </article>
          ))}
        </div>
      </section>
      <section className={styles.panel} aria-labelledby="save-collection-heading">
        <div className={styles.panelHeading}>
          <div>
            <h2 id="save-collection-heading">Save a collection</h2>
            <p>{ids.length} selected analyses · saved to your account</p>
          </div>
        </div>
        {ids.length >= 2 && ids.length <= 50 ? (
          <form onSubmit={submit} className={styles.collectionForm}>
            <label>
              Collection name
              <input
                name="name"
                required
                maxLength={80}
                placeholder="e.g. High initial resistance"
              />
            </label>
            <label>
              Research question
              <textarea
                name="question"
                maxLength={500}
                rows={4}
                placeholder="What would you like to understand?"
              />
            </label>
            <Button type="submit" loading={save.isPending}>
              Save collection
            </Button>
            {save.isError ? <ErrorState error={save.error} /> : null}
            {save.isSuccess ? <p role="status">Collection saved.</p> : null}
          </form>
        ) : (
          <EmptyState
            title="Choose at least two analyses"
            description="Build a selection before saving a research collection."
            action={<Button onClick={onChoose}>Choose analyses</Button>}
          />
        )}
      </section>
    </div>
  )
}
