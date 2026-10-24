import { useState, type FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'
import { ContentContainer } from '@/components/layout/ContentContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/Button'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import {
  allSusceptibleProfile,
  countResistant,
  profileToCode,
  toggleAntibiotic,
} from '@/domain/profile'
import { useAntibiotics } from '@/hooks/useAntibiotics'
import { sampleKeys, saveSample } from './sample-api'
import { useSamples } from './useSamples'
import { SampleList, type SampleCategory } from './SampleList'
import styles from './samples.module.css'

export function SamplesPage() {
  const [label, setLabel] = useState('')
  const [profile, setProfile] = useState(allSusceptibleProfile)
  const [category, setCategory] = useState<SampleCategory>('all')
  const [notice, setNotice] = useState('')
  const samples = useSamples()
  const antibiotics = useAntibiotics()
  const client = useQueryClient()
  const save = useMutation({
    mutationFn: saveSample,
    retry: false,
    onSuccess: (saved) => {
      setNotice(`Saved ${saved.label}. Ready to record another sample.`)
      setLabel('')
      setProfile(allSusceptibleProfile())
      void client.invalidateQueries({ queryKey: sampleKeys.all })
    },
  })
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!label.trim() || !antibiotics.data || save.isPending) return
    setNotice('')
    save.mutate({ label: label.trim(), resistanceProfile: profile })
  }
  return (
    <ContentContainer>
      <PageHeader
        title="Samples"
        subtitle="Record initial resistance profiles now. Evaluate strategies when you’re ready."
        action={<Link to="/app/history?category=pending">View sample history</Link>}
      />
      <div className={styles.layout}>
        <section className={styles.editor} aria-labelledby="record-sample-title">
          <h2 id="record-sample-title">Record a sample</h2>
          <p>Use a sample label, without patient-identifying details.</p>
          <form onSubmit={submit}>
            <label className={styles.label}>
              Sample label
              <input
                value={label}
                maxLength={80}
                required
                disabled={save.isPending}
                placeholder="e.g. UTI-024"
                onChange={(event) => {
                  setLabel(event.target.value)
                  setNotice('')
                }}
              />
            </label>
            <div className={styles.profileCode}>
              <code aria-label="Sample resistance profile">{profileToCode(profile)}</code>
              <span>{countResistant(profile)} / 7 resistant</span>
            </div>
            {antibiotics.isPending ? <LoadingState label="Loading antibiotics" lines={2} /> : null}
            {antibiotics.isError ? (
              <ErrorState error={antibiotics.error} onRetry={() => void antibiotics.refetch()} />
            ) : null}
            {antibiotics.data?.map((drug) => (
              <div key={drug.actionId} className={styles.drug}>
                <span>{drug.displayName}</span>
                <button
                  type="button"
                  role="switch"
                  aria-label={`${drug.displayName} resistant`}
                  aria-checked={profile[drug.index] === 1}
                  disabled={save.isPending}
                  onClick={() => setProfile(toggleAntibiotic(profile, drug.index))}
                >
                  <i />
                  <span>{profile[drug.index] === 1 ? 'Resistant' : 'Susceptible'}</span>
                </button>
              </div>
            ))}
            <div className={styles.formActions}>
              <Button
                type="submit"
                variant="dark"
                loading={save.isPending}
                disabled={!label.trim() || !antibiotics.data}
              >
                Save sample
              </Button>
              <Button
                variant="ghost"
                disabled={save.isPending}
                onClick={() => {
                  setProfile(allSusceptibleProfile())
                  setNotice('')
                }}
              >
                Reset profile
              </Button>
            </div>
            {save.isError ? (
              <ErrorState error={save.error} title="Sample could not be saved" />
            ) : null}
            <p className={styles.notice} role="status">
              {notice}
            </p>
          </form>
        </section>
        <section className={styles.library} aria-labelledby="sample-library-title">
          <h2 id="sample-library-title">Sample library</h2>
          <div className={styles.categories} role="group" aria-label="Sample status">
            {(['all', 'pending', 'run'] as const).map((status) => (
              <button
                type="button"
                key={status}
                aria-pressed={category === status}
                onClick={() => setCategory(status)}
              >
                {status === 'all' ? 'All' : status === 'pending' ? 'Not analyzed' : 'Analyzed'}{' '}
                <span>
                  {samples.data?.filter(
                    (sample) =>
                      status === 'all' ||
                      (status === 'pending' ? sample.runs.length === 0 : sample.runs.length > 0),
                  ).length ?? 0}
                </span>
              </button>
            ))}
          </div>
          {samples.isPending ? <LoadingState label="Loading saved samples" lines={3} /> : null}
          {samples.isError ? (
            <ErrorState error={samples.error} onRetry={() => void samples.refetch()} />
          ) : null}
          {samples.data ? <SampleList samples={samples.data} category={category} /> : null}
        </section>
      </div>
    </ContentContainer>
  )
}
