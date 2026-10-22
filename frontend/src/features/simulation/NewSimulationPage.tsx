import { useId, useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { isApiError } from '@/api/api-errors'
import { ContentContainer } from '@/components/layout/ContentContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/Button'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { StatusIndicator } from '@/components/ui/StatusIndicator'
import {
  allSusceptibleProfile,
  countResistant,
  countSusceptible,
  isAllResistant,
  parseProfileCode,
  profileToCode,
  toggleAntibiotic,
} from '@/domain/profile'
import { parseSeedInput } from '@/domain/seeds'
import { GLOSSARY } from '@/domain/terminology'
import type { CreateComparisonRequest } from '@/domain/types'
import { useAntibiotics } from '@/hooks/useAntibiotics'
import { useCreateComparison } from '@/hooks/useCreateComparison'
import { useModelMetadata } from '@/hooks/useModelMetadata'
import styles from './simulation.module.css'
import setup from './setup.module.css'

/** The input form behind "Run Simulation": a starting profile and optional seeds, then both strategies run for the fixed horizon. */
export function NewSimulationPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const environmentSeedId = useId()
  const policySeedId = useId()
  const [profile, setProfile] = useState(
    () => parseProfileCode(params.get('profile')) ?? allSusceptibleProfile(),
  )
  const [environmentSeedText, setEnvironmentSeedText] = useState('')
  const [policySeedText, setPolicySeedText] = useState('')
  const [reviewing, setReviewing] = useState(false)

  const antibiotics = useAntibiotics()
  const model = useModelMetadata()
  const create = useCreateComparison()

  const environmentSeed = parseSeedInput(environmentSeedText)
  const policySeed = parseSeedInput(policySeedText)
  const terminal = isAllResistant(profile)
  const blocked = terminal || !environmentSeed.ok || !policySeed.ok || !antibiotics.data

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (blocked || create.isPending || !environmentSeed.ok || !policySeed.ok) {
      return
    }
    if (!reviewing) {
      setReviewing(true)
      return
    }
    const request: CreateComparisonRequest = {
      resistanceProfile: profile,
      ...(environmentSeed.value === undefined ? {} : { environmentSeed: environmentSeed.value }),
      ...(policySeed.value === undefined ? {} : { policySeed: policySeed.value }),
    }
    create.mutate(request, {
      onSuccess: (comparison) => void navigate(`/app/recommendations/comparison/${comparison.id}`),
    })
  }

  const mayBeStored =
    isApiError(create.error) && (create.error.kind === 'timeout' || create.error.kind === 'network')

  return (
    <ContentContainer>
      <div className={setup.stage}>
        <div className={setup.card}>
          <div className={setup.emblem} aria-hidden="true">
            S
          </div>
          <PageHeader
            title={reviewing ? 'Review your simulation' : 'Configure your simulation'}
            subtitle={
              reviewing
                ? 'Check your starting conditions before running both strategies.'
                : 'Set a starting profile. Explore what happens next.'
            }
          />
          <form
            onSubmit={submit}
            noValidate
            aria-label="Simulation configuration"
            className={styles['formCard']}
          >
            <fieldset disabled={reviewing || create.isPending} className={setup.configuration}>
              <div className={styles['field']}>
                <div className={setup.sectionHeading}>
                  <h2 className={styles['fieldTitle']}>01 — Initial resistance profile</h2>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setProfile(allSusceptibleProfile())}
                  >
                    Reset
                  </Button>
                </div>
                <div className={setup.profileSummary} aria-live="polite">
                  <div>
                    <small>Resistance profile</small>
                    <output aria-label="Resistance profile code">{profileToCode(profile)}</output>
                  </div>
                  <div>
                    <strong>{countResistant(profile)} / 7 resistant</strong>
                    <small>{countSusceptible(profile)} susceptible</small>
                  </div>
                </div>
                {antibiotics.isPending ? (
                  <LoadingState label="Loading antibiotics" lines={2} />
                ) : null}
                {antibiotics.isError ? (
                  <ErrorState
                    error={antibiotics.error}
                    onRetry={() => void antibiotics.refetch()}
                  />
                ) : null}
                {antibiotics.data ? (
                  <div className={setup.antibiotics}>
                    {antibiotics.data.map((entry) => (
                      <div className={setup.antibiotic} key={entry.actionId}>
                        <span>{entry.displayName}</span>
                        <button
                          type="button"
                          role="switch"
                          aria-label={`${entry.displayName} resistant`}
                          aria-checked={profile[entry.index] === 1}
                          className={setup.toggle}
                          onClick={() => setProfile(toggleAntibiotic(profile, entry.index))}
                        >
                          <span className={setup.track}>
                            <span />
                          </span>
                          <span>{profile[entry.index] === 1 ? 'Resistant' : 'Susceptible'}</span>
                        </button>
                      </div>
                    ))}
                  </div>
                ) : null}
                <p className={setup.note}>
                  0 = susceptible · 1 = resistant. A binary research model, not a clinical
                  susceptibility test.
                </p>
                {terminal ? (
                  <p role="alert">
                    <StatusIndicator kind="warning" label="No feasible actions" />{' '}
                    {GLOSSARY.noFeasibleActions} Change the profile to continue.
                  </p>
                ) : null}
              </div>

              <div className={setup.strategies}>
                <h2 className={styles['fieldTitle']}>02 — Comparison strategies</h2>
                <div className={setup.policy}>
                  <span>
                    <strong>PPO · Reinforcement learning</strong>
                    <small>Learned antibiotic-selection policy</small>
                  </span>
                  <span className={setup.available}>Available</span>
                </div>
                <div className={setup.policy}>
                  <span>
                    <strong>Random Susceptible Baseline</strong>
                    <small>Randomly selects a currently susceptible antibiotic</small>
                  </span>
                  <span className={setup.included}>Included</span>
                </div>
                <span className={styles['chip']}>
                  <small>Horizon</small>
                  <strong>{model.data ? `${model.data.horizon} steps` : '8 steps'}</strong>
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
                    {!environmentSeed.ok ? (
                      <span className={styles['error']}>{environmentSeed.message}</span>
                    ) : null}
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
                    {!policySeed.ok ? (
                      <span className={styles['error']}>{policySeed.message}</span>
                    ) : null}
                  </div>
                </div>
                <p className={styles['hint']} style={{ marginTop: 'var(--space-2)' }}>
                  {GLOSSARY.sameSeed}
                </p>
              </details>
            </fieldset>

            <div className="row">
              <Button type="submit" variant="dark" loading={create.isPending} disabled={blocked}>
                {create.isPending ? 'Running' : reviewing ? 'Run Simulation' : 'Review simulation'}
              </Button>
              {reviewing ? (
                <Button
                  variant="secondary"
                  disabled={create.isPending}
                  onClick={() => setReviewing(false)}
                >
                  Edit configuration
                </Button>
              ) : null}
              <Link to="/app">Cancel</Link>
            </div>

            <div role="status" aria-live="polite" className="visually-hidden">
              {create.isPending ? 'Running the simulation. This can take a minute.' : ''}
            </div>
            {create.isPending ? (
              <LoadingState
                label="Running both strategies. This can take up to a minute."
                lines={1}
              />
            ) : null}
            {create.isError ? (
              <ErrorState error={create.error} title="The simulation could not be run">
                {mayBeStored ? (
                  <p>
                    The server may have finished and stored it anyway. Check your{' '}
                    <Link to="/app/history">history</Link> before running it again.
                  </p>
                ) : null}
              </ErrorState>
            ) : null}
          </form>
        </div>
      </div>
    </ContentContainer>
  )
}
