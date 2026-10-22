import type { ModelProvenance, RunSummary, StrategyResult } from '@/domain/types'
import { useComparison } from '@/hooks/useComparison'
import { useLatestPpoRun } from '@/hooks/useLatestPpoRun'
import { useSimulation } from '@/hooks/useSimulation'

export interface ProfileRun {
  summary: RunSummary
  provenance: ModelProvenance
  ppo: StrategyResult
  /** Present when the run was a comparison. */
  baseline: StrategyResult | null
}

export type ProfileRunState =
  | { status: 'loading' }
  | { status: 'error'; error: unknown; retry: () => void }
  | { status: 'empty' }
  | { status: 'ready'; run: ProfileRun }

/** The profile page's data: the latest stored run with a PPO result, with its steps. Nothing is invented when there is none. */
export function useProfileRun(): ProfileRunState {
  const latest = useLatestPpoRun()
  const summary = latest.run
  const comparison = useComparison(summary?.kind === 'comparison' ? summary.id : undefined)
  const simulation = useSimulation(summary?.kind === 'simulation' ? summary.id : undefined)

  if (latest.isPending) {
    return { status: 'loading' }
  }
  if (latest.isError) {
    return { status: 'error', error: latest.error, retry: latest.refetch }
  }
  if (!summary) {
    return { status: 'empty' }
  }

  const query = summary.kind === 'comparison' ? comparison : simulation
  if (query.isPending) {
    return { status: 'loading' }
  }
  if (query.isError) {
    return { status: 'error', error: query.error, retry: () => void query.refetch() }
  }

  if (comparison.data?.ppo) {
    return {
      status: 'ready',
      run: {
        summary,
        provenance: comparison.data.provenance,
        ppo: comparison.data.ppo,
        baseline: comparison.data.baseline,
      },
    }
  }
  if (simulation.data?.result?.strategy === 'ppo') {
    return {
      status: 'ready',
      run: {
        summary,
        provenance: simulation.data.provenance,
        ppo: simulation.data.result,
        baseline: null,
      },
    }
  }
  return { status: 'empty' }
}
