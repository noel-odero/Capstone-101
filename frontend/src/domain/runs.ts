import type { Comparison, RunSummary, Simulation, StrategyResult } from './types'

export function strategyResults(run: Comparison | Simulation): StrategyResult[] {
  const results = 'result' in run ? [run.result] : [run.ppo, run.dqn, run.baseline]
  return results.filter((result): result is StrategyResult => result != null)
}

/** Where a stored run is opened in the workspace; null when this interface has no view for it. */
export function runDetailPath(run: Pick<RunSummary, 'id' | 'kind' | 'strategies'>): string | null {
  if (run.kind === 'comparison') {
    return `/app/simulation/${run.id}`
  }
  return run.strategies.some(
    (strategy) => strategy.strategy === 'ppo' || strategy.strategy === 'dqn',
  )
    ? `/app/recommendations/simulation/${run.id}`
    : null
}
