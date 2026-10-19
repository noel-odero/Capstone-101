import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router'
import { isApiError } from '@/api/api-errors'
import { ContentContainer } from '@/components/layout/ContentContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { OutcomeSummary } from '@/components/scientific/OutcomeSummary'
import { ScientificLimitationsNotice } from '@/components/scientific/ScientificLimitationsNotice'
import { ButtonLink } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { buildMetricRows, formatMetricValue } from '@/domain/metrics'
import { formatProfileSummary } from '@/domain/formatters'
import { profileToCode } from '@/domain/profile'
import { STRATEGY_NAMES } from '@/domain/terminology'
import type { Comparison, ResistanceProfile } from '@/domain/types'
import { useAntibiotics } from '@/hooks/useAntibiotics'
import { useComparison } from '@/hooks/useComparison'
import { useRecommendation } from '@/hooks/useRecommendation'
import { useSimulation } from '@/hooks/useSimulation'
import { SequenceCard } from './SequenceCard'
import { useStepParam } from './useStepParam'
import styles from './recommendation.module.css'

function Frame({ children, initialProfile }: { children: ReactNode; initialProfile?: ResistanceProfile }) {
  return (
    <ContentContainer>
      <PageHeader
        title="Recommendations"
        subtitle="The PPO-selected sequence, shown with the alternative from the same run."
        action={
          <ButtonLink to={initialProfile ? `/app/simulation/new?profile=${profileToCode(initialProfile)}` : '/app/simulation/new'} variant="dark">
            Run New Simulation
          </ButtonLink>
        }
      />
      {children}
    </ContentContainer>
  )
}

function NotFound({ title }: { title: string }) {
  return (
    <Frame>
      <EmptyState title={title} description="Open a run from your history, or start a new simulation." action={<ButtonLink to="/app/history">Go to history</ButtonLink>} />
    </Frame>
  )
}

function Outcomes({ comparison }: { comparison: Comparison }) {
  const { ppo, baseline } = comparison
  if (!ppo || !baseline) {
    return null
  }
  const rows = buildMetricRows(ppo.metrics, baseline.metrics)
  return (
    <Card aria-labelledby="outcomes-title">
      <CardHeader titleId="outcomes-title" title="Outcomes of each sequence" description="Returned simulation metrics. They describe the simulator, not patients." />
      <div className="scroll-x">
        <table className={styles['outcomes']}>
          <caption className="visually-hidden">Outcomes of the PPO-selected sequence and the baseline sequence</caption>
          <thead>
            <tr>
              <th scope="col">Metric</th>
              <th scope="col">PPO</th>
              <th scope="col">Baseline</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key}>
                <th scope="row">{row.label}</th>
                <td>{formatMetricValue(row.key, row.ppo)}</td>
                <td>{formatMetricValue(row.key, row.baseline)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function ComparisonRecommendation({ id }: { id: string }) {
  const comparison = useComparison(id)
  const antibiotics = useAntibiotics()
  const [step, setStep] = useStepParam()

  if (comparison.isPending || antibiotics.isPending) {
    return (
      <Frame>
        <LoadingState label="Loading the sequences" lines={3} block />
      </Frame>
    )
  }
  if (comparison.isError) {
    return isApiError(comparison.error) && comparison.error.kind === 'not_found' ? (
      <NotFound title="No simulation has this ID" />
    ) : (
      <Frame>
        <ErrorState error={comparison.error} onRetry={() => void comparison.refetch()} />
      </Frame>
    )
  }
  if (antibiotics.isError) {
    return (
      <Frame>
        <ErrorState error={antibiotics.error} title="The antibiotic catalogue could not be loaded" onRetry={() => void antibiotics.refetch()} />
      </Frame>
    )
  }

  const { data } = comparison
  const { ppo, baseline } = data
  if (data.status !== 'completed' || !ppo || !baseline) {
    return <NotFound title="This simulation has no sequences" />
  }

  return (
    <Frame initialProfile={ppo.initialProfile}>
      <p className="muted" style={{ marginBottom: 'var(--space-4)' }}>
        Initial profile <strong style={{ fontFamily: 'var(--font-mono)', letterSpacing: '0.1em' }}>{profileToCode(ppo.initialProfile)}</strong> (
        {formatProfileSummary(ppo.initialProfile)}) &middot; <Link to={`/app/simulation/${data.id}`}>Open the simulation</Link>
      </p>
      <div className="stack-lg">
        <div className={styles['grid']}>
          <SequenceCard
            title="PPO-selected sequence"
            badge="PPO-selected"
            highlighted
            initialProfile={ppo.initialProfile}
            steps={ppo.steps}
            terminationReason={ppo.terminationReason}
            antibiotics={antibiotics.data}
            selectedStep={step}
            onSelectStep={setStep}
            verb={`${STRATEGY_NAMES.ppo} selected`}
          />
          <SequenceCard
            title="Random Susceptible Baseline sequence"
            initialProfile={baseline.initialProfile}
            steps={baseline.steps}
            terminationReason={baseline.terminationReason}
            antibiotics={antibiotics.data}
            selectedStep={step}
            onSelectStep={setStep}
            verb={`${STRATEGY_NAMES.random_susceptible_baseline} sampled`}
          />
        </div>
        <Outcomes comparison={data} />
        <p className="muted" style={{ fontSize: 'var(--text-xs)' }}>
          {data.singleRunCaveat}
        </p>
        <ScientificLimitationsNotice />
      </div>
    </Frame>
  )
}

function SimulationRecommendation({ id }: { id: string }) {
  const recommendation = useRecommendation(id)
  const simulation = useSimulation(recommendation.data ? id : undefined)
  const antibiotics = useAntibiotics()
  const [step, setStep] = useStepParam()

  if (recommendation.isPending || antibiotics.isPending) {
    return (
      <Frame>
        <LoadingState label="Loading the sequence" lines={3} block />
      </Frame>
    )
  }
  if (recommendation.isError) {
    return isApiError(recommendation.error) && recommendation.error.kind === 'not_found' ? (
      <NotFound title="No PPO sequence exists for this simulation" />
    ) : (
      <Frame>
        <ErrorState error={recommendation.error} onRetry={() => void recommendation.refetch()} />
      </Frame>
    )
  }
  if (antibiotics.isError) {
    return (
      <Frame>
        <ErrorState error={antibiotics.error} title="The antibiotic catalogue could not be loaded" onRetry={() => void antibiotics.refetch()} />
      </Frame>
    )
  }

  const { data } = recommendation
  return (
    <Frame initialProfile={data.initialProfile}>
      <div className="stack-lg">
        <SequenceCard
          title="PPO-selected sequence"
          badge="PPO-selected"
          highlighted
          initialProfile={data.initialProfile}
          steps={data.steps}
          terminationReason={data.terminationReason}
          antibiotics={antibiotics.data}
          selectedStep={step}
          onSelectStep={setStep}
          verb={`${STRATEGY_NAMES.ppo} selected`}
        />
        {simulation.data?.result ? (
          <Card aria-labelledby="sim-outcome-title">
            <CardHeader titleId="sim-outcome-title" title="Outcome of this sequence" />
            <OutcomeSummary result={simulation.data.result} definitions={simulation.data.metricDefinitions} />
          </Card>
        ) : simulation.isError ? (
          <ErrorState error={simulation.error} title="The run's metrics could not be loaded" onRetry={() => void simulation.refetch()} />
        ) : (
          <LoadingState label="Loading the run's metrics" lines={2} />
        )}
        <p className="muted" style={{ fontSize: 'var(--text-xs)' }}>
          {data.interpretation}
        </p>
        <ScientificLimitationsNotice />
      </div>
    </Frame>
  )
}

/**
 * `/app/recommendations/comparison/:id` reads a stored comparison (PPO and the baseline); `/app/recommendations/simulation/:id`
 * reads the recommendation of a stored PPO simulation. Neither creates a new run.
 */
export function RecommendationPage() {
  const params = useParams()
  if (params['comparisonId']) {
    return <ComparisonRecommendation id={params['comparisonId']} />
  }
  if (params['simulationId']) {
    return <SimulationRecommendation id={params['simulationId']} />
  }
  return <NotFound title="Nothing to show" />
}

