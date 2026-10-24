import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router'
import { inspectProfile } from '@/api/profile-api'
import { ContentContainer } from '@/components/layout/ContentContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { ButtonLink } from '@/components/ui/Button'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { allSusceptibleProfile, parseProfileCode } from '@/domain/profile'
import { useAntibiotics } from '@/hooks/useAntibiotics'
import { useModelMetadata } from '@/hooks/useModelMetadata'
import { MODEL_STATES } from './model-states'
import { StateSpace } from './StateSpace'
import { TransitionEvidence } from './TransitionEvidence'
import { RelatedResearch } from './RelatedResearch'
import styles from './model-explorer.module.css'

export function ProfilePage() {
  const [params, setParams] = useSearchParams()
  const requestedCount = params.get('count')
  const filter =
    requestedCount !== null && /^[0-7]$/.test(requestedCount) ? Number(requestedCount) : null
  const requestedState = parseProfileCode(params.get('state')) ? params.get('state') : '0000000'
  const initialState = MODEL_STATES.find((state) => state.code === requestedState) ?? {
    code: '0000000',
    profile: allSusceptibleProfile(),
    count: 0,
  }
  const state =
    filter !== null && initialState.count !== filter
      ? (MODEL_STATES.find((state) => state.count === filter) ?? initialState)
      : initialState
  const { code: selected, profile } = state
  const antibiotics = useAntibiotics()
  const model = useModelMetadata()
  const evidence = useQuery({
    queryKey: ['model-state-evidence', selected, model.data?.interactionDataSha256],
    queryFn: ({ signal }) => inspectProfile(profile, signal),
    enabled: !!model.data,
    staleTime: 5 * 60_000,
  })
  function select(code: string) {
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous)
        next.set('state', code)
        const state = MODEL_STATES.find((state) => state.code === code)
        if (filter !== null && state?.count !== filter) next.delete('count')
        return next
      },
      { preventScrollReset: true },
    )
  }
  function changeFilter(count: number | null) {
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous)
        if (count === null) next.delete('count')
        else {
          next.set('count', String(count))
          if (MODEL_STATES.find((state) => state.code === selected)?.count !== count)
            next.set('state', MODEL_STATES.find((state) => state.count === count)?.code ?? selected)
        }
        return next
      },
      { preventScrollReset: true },
    )
  }
  return (
    <ContentContainer>
      <div className={styles.explorer}>
        <PageHeader
          title="E. coli Model Explorer"
          subtitle="Explore the model’s resistance states and transition evidence."
          action={
            <ButtonLink to="/methodology" variant="ghost" size="sm">
              Model methodology
            </ButtonLink>
          }
        />
        <div className={styles.modelSummary}>
          <span>128 possible states</span>
          <span>7 antibiotics</span>
          {model.data ? <span>{model.data.horizon}-step horizon</span> : null}
          <span className={styles.readOnly}>Model reference · read only</span>
        </div>
        <div className={styles.explorerGrid}>
          <StateSpace
            selected={selected}
            filter={filter}
            onSelect={select}
            onFilter={changeFilter}
          />
          <section className={styles.evidencePanel} aria-labelledby="selected-state-heading">
            <div className={styles.selectedHeading}>
              <div>
                <span className={styles.eyebrow}>02 / SELECTED STATE</span>
                <h2 id="selected-state-heading">{selected}</h2>
              </div>
              <ButtonLink to={`/app/simulation/new?profile=${selected}`} size="sm">
                Evaluate this state
              </ButtonLink>
            </div>
            {model.isPending || antibiotics.isPending ? (
              <LoadingState label="Loading model definitions" lines={3} />
            ) : null}
            {model.isError ? (
              <ErrorState error={model.error} onRetry={() => void model.refetch()} />
            ) : null}
            {antibiotics.isError ? (
              <ErrorState error={antibiotics.error} onRetry={() => void antibiotics.refetch()} />
            ) : null}
            {evidence.isFetching && !evidence.data ? (
              <LoadingState label="Checking transition evidence" lines={4} />
            ) : null}
            {evidence.isError ? (
              <ErrorState
                error={evidence.error}
                title="Transition evidence could not be checked"
                onRetry={() => void evidence.refetch()}
              />
            ) : null}
            {evidence.data && antibiotics.data ? (
              <TransitionEvidence
                key={selected}
                data={evidence.data}
                entries={antibiotics.data}
                onSelect={select}
              />
            ) : null}
          </section>
        </div>
        <RelatedResearch key={selected} code={selected} />
      </div>
    </ContentContainer>
  )
}
