import { Link } from 'react-router'
import { ButtonLink } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { MetricCard } from '@/components/ui/MetricCard'
import { formatDateTime, shortId } from '@/domain/formatters'
import { formatMetricValue, metricDefinitionFor, type MetricKey } from '@/domain/metrics'
import { profileToCode } from '@/domain/profile'
import { runDetailPath } from '@/domain/runs'
import { STRATEGY_NAMES } from '@/domain/terminology'
import type { Comparison, MetricDefinitions, RunSummary, Simulation, StrategyMetrics } from '@/domain/types'
import { useComparison } from '@/hooks/useComparison'
import { RECENT_RUNS_PAGE_SIZE, useRecentRuns } from '@/hooks/useRecentRuns'
import { useSimulation } from '@/hooks/useSimulation'
import styles from './dashboard.module.css'

interface CardSpec {
  key: MetricKey
  label: string
  caption: string
}

/** Four headline numbers. Labels say what is measured; none of them is a clinical outcome. */
const CARDS: readonly CardSpec[] = [
  { key: 'cumulativeResistanceBurden', label: 'Resistance burden', caption: 'Lower is less simulated burden' },
  { key: 'resistanceEmergenceRate', label: 'Emergence rate', caption: 'Share of steps where resistance rose' },
  { key: 'susceptibleActionRate', label: 'Susceptible-action rate', caption: 'Set by the action mask, not efficacy' },
  { key: 'finalSusceptibleCount', label: 'Remaining susceptible', caption: 'Antibiotics out of 7' },
]

interface LatestData {
  primary: StrategyMetrics | null
  primaryLabel: string
  baseline: StrategyMetrics | null
  definitions: MetricDefinitions
}

function fromComparison(comparison: Comparison): LatestData {
  return {
    primary: comparison.ppo?.metrics ?? null,
    primaryLabel: STRATEGY_NAMES.ppo,
    baseline: comparison.baseline?.metrics ?? null,
    definitions: comparison.metricDefinitions,
  }
}

function fromSimulation(simulation: Simulation): LatestData {
  const result = simulation.result
  return {
    primary: result?.metrics ?? null,
    primaryLabel: result ? STRATEGY_NAMES[result.strategy] : STRATEGY_NAMES.ppo,
    baseline: null,
    definitions: simulation.metricDefinitions,
  }
}

function Cards({ latest, data }: { latest: RunSummary; data: LatestData }) {
  const path = runDetailPath(latest)
  return (
    <>
      <p className={styles['latest']}>
        Latest {latest.kind === 'comparison' ? 'comparison' : 'simulation'}{' '}
        {path ? <Link to={path}>{shortId(latest.id)}</Link> : shortId(latest.id)} &middot; profile{' '}
        <span style={{ fontFamily: 'var(--font-mono)', letterSpacing: '0.1em' }}>{profileToCode(latest.initialProfile)}</span> &middot;{' '}
        {formatDateTime(latest.createdAtUtc)}
      </p>
      <div className={styles['metrics']}>
        {CARDS.map(({ key, label, caption }) => (
          <MetricCard
            key={key}
            label={label}
            value={data.primary ? formatMetricValue(key, data.primary[key]) : null}
            caption={`${data.primaryLabel}. ${caption}`}
            definition={metricDefinitionFor(data.definitions, key)?.definition}
            secondary={
              data.baseline ? (
                <span>
                  Baseline <strong>{formatMetricValue(key, data.baseline[key])}</strong>
                </span>
              ) : null
            }
          />
        ))}
      </div>
    </>
  )
}

function LatestComparison({ latest }: { latest: RunSummary }) {
  const query = useComparison(latest.id)
  if (query.isPending) {
    return <LoadingState label="Loading the latest run" lines={2} block />
  }
  if (!query.data) {
    return <ErrorState error={query.error} title="The latest run could not be loaded" onRetry={() => void query.refetch()} />
  }
  return <Cards latest={latest} data={fromComparison(query.data)} />
}

function LatestSimulation({ latest }: { latest: RunSummary }) {
  const query = useSimulation(latest.id)
  if (query.isPending) {
    return <LoadingState label="Loading the latest run" lines={2} block />
  }
  if (!query.data) {
    return <ErrorState error={query.error} title="The latest run could not be loaded" onRetry={() => void query.refetch()} />
  }
  return <Cards latest={latest} data={fromSimulation(query.data)} />
}

/** Metrics of the latest stored run, read from the API. With no runs there is an invitation, never a number. */
export function OverviewMetrics() {
  const recent = useRecentRuns(1, RECENT_RUNS_PAGE_SIZE)
  const latest = recent.data?.items[0]

  if (recent.isPending) {
    return <LoadingState label="Loading your latest run" lines={2} block />
  }
  if (recent.isError) {
    return <ErrorState error={recent.error} title="Your runs could not be loaded" onRetry={() => void recent.refetch()} />
  }
  if (!latest) {
    return (
      <EmptyState
        title="No simulations yet"
        description="Run your first simulation to see its metrics here."
        action={<ButtonLink to="/app/simulation/new">Run Simulation</ButtonLink>}
      />
    )
  }
  return latest.kind === 'comparison' ? <LatestComparison key={latest.id} latest={latest} /> : <LatestSimulation key={latest.id} latest={latest} />
}
