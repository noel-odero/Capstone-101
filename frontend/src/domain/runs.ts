import type { RunSummary } from './types'

/** Where a stored run is opened in the workspace; null when this interface has no view for it. */
export function runDetailPath(run: Pick<RunSummary, 'id' | 'kind' | 'strategies'>): string | null {
  if (run.kind === 'comparison') {
    return `/app/simulation/${run.id}`
  }
  return run.strategies.some((strategy) => strategy.strategy === 'ppo')
    ? `/app/recommendations/simulation/${run.id}`
    : null
}

/** The recommendation view of a stored run (the PPO-selected sequence); null when the run has no PPO result. */
export function recommendationPath(
  run: Pick<RunSummary, 'id' | 'kind' | 'strategies'>,
): string | null {
  if (!run.strategies.some((strategy) => strategy.strategy === 'ppo')) {
    return null
  }
  return run.kind === 'comparison'
    ? `/app/recommendations/comparison/${run.id}`
    : `/app/recommendations/simulation/${run.id}`
}
