import type { RunSummary } from '@/domain/types'
import { figuresFrom, type RunFigures } from '@/domain/homeFigures'
import { useComparison } from '@/hooks/useComparison'
import { RECENT_RUNS_PAGE_SIZE, useRecentRuns } from '@/hooks/useRecentRuns'
import { useSimulation } from '@/hooks/useSimulation'

const hasPpo = (run: RunSummary) => run.strategies.some((strategy) => strategy.strategy === 'ppo')

function usePpoFigures(run: RunSummary | undefined) {
  const comparison = useComparison(run?.kind === 'comparison' ? run.id : undefined)
  const simulation = useSimulation(run?.kind === 'simulation' ? run.id : undefined)
  const query = run?.kind === 'comparison' ? comparison : simulation
  const result = comparison.data?.ppo ?? (simulation.data?.result?.strategy === 'ppo' ? simulation.data.result : null)
  return {
    pending: run !== undefined && query.isPending,
    error: run !== undefined && query.isError ? query.error : null,
    figures: result ? figuresFrom(result) : null,
  }
}

export type HomeMetricsState =
  | { status: 'loading' }
  | { status: 'error'; error: unknown; retry: () => void }
  | { status: 'empty' }
  | { status: 'ready'; latest: RunFigures; previous: RunFigures | null }

/** The latest stored run with a PPO result, and the one before it for the change since last time. */
export function useHomeMetrics(): HomeMetricsState {
  const recent = useRecentRuns(1, RECENT_RUNS_PAGE_SIZE)
  const [latestRun, previousRun] = (recent.data?.items ?? []).filter(hasPpo)
  const latest = usePpoFigures(latestRun)
  const previous = usePpoFigures(previousRun)

  if (recent.isPending || latest.pending || previous.pending) {
    return { status: 'loading' }
  }
  const error = recent.isError ? recent.error : latest.error ?? previous.error
  if (error) {
    return { status: 'error', error, retry: () => void recent.refetch() }
  }
  return latest.figures ? { status: 'ready', latest: latest.figures, previous: previous.figures } : { status: 'empty' }
}
