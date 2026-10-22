import type { RunSummary } from '@/domain/types'
import { RECENT_RUNS_PAGE_SIZE, useRecentRuns } from '@/hooks/useRecentRuns'

const hasPpo = (run: RunSummary) => run.strategies.some((strategy) => strategy.strategy === 'ppo')

/** The newest stored run that has a PPO result: the one the profile page, the tabs and the home page describe. */
export function useLatestPpoRun() {
  const recent = useRecentRuns(1, RECENT_RUNS_PAGE_SIZE)
  return {
    isPending: recent.isPending,
    isError: recent.isError,
    error: recent.error,
    refetch: () => void recent.refetch(),
    run: recent.data?.items.find(hasPpo) ?? null,
  }
}
