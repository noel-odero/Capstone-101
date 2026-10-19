import { useId, useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { isApiError } from '@/api/api-errors'
import { ContentContainer } from '@/components/layout/ContentContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { ProfileEditor } from '@/components/scientific/ProfileEditor'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { StatusIndicator } from '@/components/ui/StatusIndicator'
import { allSusceptibleProfile, countResistant, countSusceptible, isAllResistant, parseProfileCode, profileToCode } from '@/domain/profile'
import { parseSeedInput } from '@/domain/seeds'
import { GLOSSARY } from '@/domain/terminology'
import type { CreateComparisonRequest } from '@/domain/types'
import { useAntibiotics } from '@/hooks/useAntibiotics'
import { useCreateComparison } from '@/hooks/useCreateComparison'
import { useModelMetadata } from '@/hooks/useModelMetadata'
import { useProfileValidation } from '@/hooks/useProfileValidation'
import styles from './simulation.module.css'

/** The input form behind "Run Simulation": a starting profile and optional seeds, then both strategies run for the fixed horizon. */
export function NewSimulationPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const environmentSeedId = useId()
  const policySeedId = useId()
  const [profile, setProfile] = useState(() => parseProfileCode(params.get('profile')) ?? allSusceptibleProfile())
  const [environmentSeedText, setEnvironmentSeedText] = useState('')
  const [policySeedText, setPolicySeedText] = useState('')

  const antibiotics = useAntibiotics()
  const model = useModelMetadata()
  const validation = useProfileValidation(profile)
  const create = useCreateComparison()

  const environmentSeed = parseSeedInput(environmentSeedText)
  const policySeed = parseSeedInput(policySeedText)
  const terminal = isAllResistant(profile)
  const blocked = terminal || !environmentSeed.ok || !policySeed.ok

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (blocked || create.isPending || !environmentSeed.ok || !policySeed.ok) {
      return
    }
    const request: CreateComparisonRequest = {
      resistanceProfile: profile,
      ...(environmentSeed.value === undefined ? {} : { environmentSeed: environmentSeed.value }),
      ...(policySeed.value === undefined ? {} : { policySeed: policySeed.value }),
    }
    create.mutate(request, { onSuccess: (comparison) => void navigate(`/app/simulation/${comparison.id}`) })
  }

  const mayBeStored = isApiError(create.error) && (create.error.kind === 'timeout' || create.error.kind === 'network')

  return (
    <ContentContainer>
      <PageHeader title="New simulation" subtitle="Choose a starting profile. PPO and the random baseline both run from it." />
      <Card as="div" className={styles['formCard']}>
        <form onSubmit={submit} noValidate aria-label="New simulation" className={styles['formCard']}>
          <div className={styles['field']}>
            <h2 className={styles['fieldTitle']}>Initial profile</h2>
            {antibiotics.isPending ? <LoadingState label="Loading antibiotics" lines={2} /> : null}
            {antibiotics.isError ? <ErrorState error={antibiotics.error} onRetry={() => void antibiotics.refetch()} /> : null}
            {antibiotics.data ? <ProfileEditor entries={antibiotics.data} profile={profile} onChange={setProfile} /> : null}
            <p className="muted tabular">
              {countSusceptible(profile)} susceptible &middot; {countResistant(profile)} resistant
              {validation.data && !validation.data.isTerminal ? <> &middot; {validation.data.feasibleActions.length} feasible actions</> : null}
            </p>
            {terminal ? (
              <p role="alert">
                <StatusIndicator kind="warning" label="No feasible actions" /> {GLOSSARY.noFeasibleActions} Change the profile to continue.
              </p>
            ) : null}
          </div>

          <div className={styles['readonly']}>
            <span className={styles['chip']}>
              <small>Horizon</small>
              <strong>{model.data ? `${model.data.horizon} steps` : '8 steps'}</strong>
            </span>
            <span className={styles['chip']}>
              <small>Strategies</small>
              <strong>PPO and Random Susceptible Baseline</strong>
            </span>
            <span className={styles['chip']}>
              <small>Profile code</small>
              <strong className={styles['mono']}>{profileToCode(profile)}</strong>
            </span>
          </div>

          <details>
            <summary>Seeds (optional)</summary>
            <div className={styles['seeds']} style={{ marginTop: 'var(--space-3)' }}>
              <div className={styles['field']}>
                <label className={styles['fieldTitle']} htmlFor={environmentSeedId}>
                  Environment seed
                </label>
                <input
                  id={environmentSeedId}
                  className={styles['input']}
                  value={environmentSeedText}
                  inputMode="numeric"
                  placeholder="Generated for you"
                  autoComplete="off"
                  aria-invalid={!environmentSeed.ok}
                  onChange={(event) => setEnvironmentSeedText(event.target.value)}
                />
                {!environmentSeed.ok ? <span className={styles['error']}>{environmentSeed.message}</span> : null}
              </div>
              <div className={styles['field']}>
                <label className={styles['fieldTitle']} htmlFor={policySeedId}>
                  Baseline policy seed
                </label>
                <input
                  id={policySeedId}
                  className={styles['input']}
                  value={policySeedText}
                  inputMode="numeric"
                  placeholder="Generated for you"
                  autoComplete="off"
                  aria-invalid={!policySeed.ok}
                  onChange={(event) => setPolicySeedText(event.target.value)}
                />
                {!policySeed.ok ? <span className={styles['error']}>{policySeed.message}</span> : null}
              </div>
            </div>
            <p className={styles['hint']} style={{ marginTop: 'var(--space-2)' }}>
              {GLOSSARY.sameSeed}
            </p>
          </details>

          <div className="row">
            <Button type="submit" variant="dark" loading={create.isPending} disabled={blocked}>
              {create.isPending ? 'Running' : 'Run Simulation'}
            </Button>
            <Link to="/app">Cancel</Link>
          </div>

          <div role="status" aria-live="polite" className="visually-hidden">
            {create.isPending ? 'Running the simulation. This can take a minute.' : ''}
          </div>
          {create.isPending ? <LoadingState label="Running both strategies. This can take up to a minute." lines={1} /> : null}
          {create.isError ? (
            <ErrorState error={create.error} title="The simulation could not be run">
              {mayBeStored ? (
                <p>
                  The server may have finished and stored it anyway. Check your <Link to="/app/history">history</Link> before running it again.
                </p>
              ) : null}
            </ErrorState>
          ) : null}
        </form>
      </Card>
    </ContentContainer>
  )
}
