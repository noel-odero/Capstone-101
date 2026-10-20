import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { isApiError } from '@/api/api-errors'
import { ContentContainer } from '@/components/layout/ContentContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { ScientificLimitationsNotice } from '@/components/scientific/ScientificLimitationsNotice'
import { ButtonLink } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { StatusIndicator } from '@/components/ui/StatusIndicator'
import { formatProfileSummary } from '@/domain/formatters'
import { profileToCode } from '@/domain/profile'
import { GLOSSARY } from '@/domain/terminology'
import { useAntibiotics } from '@/hooks/useAntibiotics'
import { useComparison } from '@/hooks/useComparison'
import { StatePanel } from './StatePanel'
import { TrajectoryChart } from './TrajectoryChart'
import styles from './simulation.module.css'

/** A stored comparison: PPO and the Random Susceptible Baseline from the same profile across the fixed horizon. */
export function SimulationPage() {
  const { comparisonId } = useParams()
  const comparison = useComparison(comparisonId)
  const antibiotics = useAntibiotics()
  const [selectedStep, setSelectedStep] = useState(1)

  if (comparison.isPending) {
    return (
      <ContentContainer>
        <PageHeader title="Simulation" />
        <LoadingState label="Loading the simulation" lines={4} block />
      </ContentContainer>
    )
  }
  if (comparison.isError) {
    const missing = isApiError(comparison.error) && comparison.error.kind === 'not_found'
    return (
      <ContentContainer>
        <PageHeader title="Simulation" />
        <ErrorState error={comparison.error} title={missing ? 'No simulation has this ID' : undefined} onRetry={missing ? undefined : () => void comparison.refetch()}>
          <ButtonLink to="/app/simulation/new" variant="secondary" size="sm">
            Start a new simulation
          </ButtonLink>
        </ErrorState>
      </ContentContainer>
    )
  }

  const { data } = comparison
  const { ppo, baseline } = data
  if (data.status !== 'completed' || !ppo || !baseline) {
    return (
      <ContentContainer>
        <PageHeader title="Simulation" />
        <EmptyState title="This simulation did not complete" description={data.error?.message ?? 'No results were returned.'} action={<ButtonLink to="/app/simulation/new">Run Simulation</ButtonLink>} />
      </ContentContainer>
    )
  }

  const code = profileToCode(ppo.initialProfile)
  const noSteps = ppo.steps.length === 0 && baseline.steps.length === 0

  return (
    <ContentContainer>
      <PageHeader title="Simulation" subtitle="PPO and the Random Susceptible Baseline from the same profile." action={<ButtonLink to={`/app/simulation/new?profile=${code}`} variant="dark">Run Simulation</ButtonLink>} />

      <div className={styles['controls']}>
        <span className={styles['chip']}>
          <small>Initial profile</small>
          <strong>
            <span className={styles['mono']}>{code}</span> <span className="muted">{formatProfileSummary(ppo.initialProfile)}</span>
          </strong>
        </span>
        <span className={styles['chip']}>
          <small>Horizon</small>
          <strong>{data.provenance.horizon} steps</strong>
        </span>
        <Link to={`/app/recommendations/comparison/${data.id}`}>See the PPO-selected sequence</Link>
      </div>

      {noSteps ? (
        <Card as="div">
          <p role="note">
            <StatusIndicator kind="warning" label="No feasible actions remain" /> {GLOSSARY.noFeasibleActions} Neither strategy took a step.
          </p>
        </Card>
      ) : antibiotics.data ? (
        <div className={styles['grid']}>
          <StatePanel ppo={ppo} baseline={baseline} antibiotics={antibiotics.data} selectedStep={selectedStep} onSelectStep={setSelectedStep} />
          <div className={styles['side']}>
            <Card aria-labelledby="chart-title">
              <CardHeader titleId="chart-title" title="Resistance trajectory" />
              <TrajectoryChart ppo={ppo} baseline={baseline} selectedStep={selectedStep} onSelectStep={setSelectedStep} />
            </Card>
          </div>
        </div>
      ) : antibiotics.isError ? (
        <ErrorState error={antibiotics.error} title="The antibiotic catalogue could not be loaded" onRetry={() => void antibiotics.refetch()} />
      ) : (
        <LoadingState label="Loading the antibiotic catalogue" lines={3} block />
      )}

      <div style={{ marginTop: 'var(--space-5)' }}>
        <ScientificLimitationsNotice />
      </div>
      <p className="muted" style={{ marginTop: 'var(--space-3)', fontSize: 'var(--text-xs)' }}>
        {data.disclaimer}
      </p>
    </ContentContainer>
  )
}
