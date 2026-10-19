import type { RunSummary } from './types'

/** Where a stored run is opened in the workspace; null when this interface has no view for it. */
export function runDetailPath(run: Pick<RunSummary, 'id' | 'kind' | 'strategies'>): string | null {
  if (run.kind === 'comparison') {
    return `/app/simulation/${run.id}`
  }
  return run.strategies.some((strategy) => strategy.strategy === 'ppo') ? `/app/recommendations/simulation/${run.id}` : null
}

export function firstName(displayName: string | undefined): string {
  const first = displayName?.trim().split(/\s+/)[0]
  return first && first.length > 0 ? first : 'there'
}
