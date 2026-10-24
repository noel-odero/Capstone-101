import type { StrategyId } from '@/domain/types'
import { comparePolicyTraces } from '@/domain/metrics'
import type { SavedAnalysis } from './history-api'

export const INSIGHT_POLICIES: StrategyId[] = ['ppo', 'dqn', 'random_susceptible_baseline']
export type Investigation =
  | 'all'
  | 'policy_failure'
  | 'ppo_worse'
  | 'dqn_worse'
  | 'baseline_lower'
  | 'agreement'
  | 'unsupported'
export const INVESTIGATION_LABELS: Record<Investigation, string> = {
  all: 'All selected evidence',
  ppo_worse: 'PPO burden above baseline',
  dqn_worse: 'DQN burden above baseline',
  policy_failure: 'A learned policy above baseline',
  baseline_lower: 'Baseline below both policies',
  agreement: 'PPO and DQN burden ties',
  unsupported: 'Transition-data gaps',
}

export function policyResult(run: SavedAnalysis, policy: StrategyId) {
  return run.strategies.find((result) => result.strategy === policy)
}

export function matchesInvestigation(run: SavedAnalysis, filter: Investigation) {
  if (filter === 'all') return true
  if (filter === 'unsupported')
    return run.strategies.some((result) => result.metrics.unsupportedStepCount > 0)
  if (run.kind !== 'comparison' || run.comparisonVerified !== true) return false
  const ppo = policyResult(run, 'ppo')?.metrics.cumulativeResistanceBurden
  const dqn = policyResult(run, 'dqn')?.metrics.cumulativeResistanceBurden
  const baseline = policyResult(run, 'random_susceptible_baseline')?.metrics
    .cumulativeResistanceBurden
  if (filter === 'policy_failure')
    return (
      baseline != null &&
      ((ppo != null && ppo > baseline + 1e-9) || (dqn != null && dqn > baseline + 1e-9))
    )
  if (filter === 'ppo_worse') return ppo != null && baseline != null && ppo > baseline + 1e-9
  if (filter === 'dqn_worse') return dqn != null && baseline != null && dqn > baseline + 1e-9
  if (filter === 'baseline_lower')
    return ppo != null && dqn != null && baseline != null && baseline < Math.min(ppo, dqn) - 1e-9
  return ppo != null && dqn != null && Math.abs(ppo - dqn) < 1e-9
}

export function summarizeEvidence(records: SavedAnalysis[]) {
  const totalSteps = records.reduce(
    (sum, run) =>
      sum + run.strategies.reduce((value, result) => value + result.metrics.treatmentSteps, 0),
    0,
  )
  const unsupported = records.reduce(
    (sum, run) =>
      sum +
      run.strategies.reduce((value, result) => value + result.metrics.unsupportedStepCount, 0),
    0,
  )
  const paired = records.filter(
    (run) =>
      run.comparisonVerified && INSIGHT_POLICIES.every((policy) => policyResult(run, policy)),
  )
  const gaps = records.filter((run) => matchesInvestigation(run, 'unsupported'))
  const ties = records.filter((run) => matchesInvestigation(run, 'agreement'))
  const differentChoices = ties.filter((run) => {
    const ppo = policyResult(run, 'ppo')
    const dqn = policyResult(run, 'dqn')
    return ppo && dqn && !comparePolicyTraces(ppo, dqn).sameChoices
  })
  const baselineLower = records.filter(
    (run) => matchesInvestigation(run, 'ppo_worse') || matchesInvestigation(run, 'dqn_worse'),
  )
  const groups = new Map<string, SavedAnalysis[]>()
  for (const run of records) {
    const key = run.initialProfile.join('')
    groups.set(key, [...(groups.get(key) ?? []), run])
  }
  const profiles = [...groups.entries()]
    .map(([profile, analyses]) => ({
      profile,
      analyses,
      hasRepeatedPolicy: INSIGHT_POLICIES.some(
        (policy) => analyses.filter((run) => policyResult(run, policy)).length >= 2,
      ),
      varying: INSIGHT_POLICIES.some((policy) => {
        const values = analyses.flatMap((run) => {
          const value = policyResult(run, policy)?.metrics.cumulativeResistanceBurden
          return value == null ? [] : [value]
        })
        return new Set(values).size > 1
      }),
    }))
    .sort((a, b) => Number(b.varying) - Number(a.varying) || b.analyses.length - a.analyses.length)
  return { totalSteps, unsupported, paired, gaps, ties, differentChoices, baselineLower, profiles }
}
