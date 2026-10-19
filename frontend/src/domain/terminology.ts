import type { StepTrace, StrategyId } from './types'

/**
 * Every user-facing scientific label lives here so no page can describe the same thing in different words.
 * The three concepts below are kept apart on purpose: what the policy selected, whether the simulator has
 * transition data for it, and what the simulator then did.
 */

export const APP_NAME = 'AMR Decision Support'
export const APP_SUBTITLE = 'Explore how antibiotic sequencing affects simulated resistance.'
export const PROTOTYPE_STATEMENT =
  'A research and educational prototype. Results come from a simplified simulation and are not clinical treatment guidance.'

export const STRATEGY_NAMES: Readonly<Record<StrategyId, string>> = {
  ppo: 'PPO',
  random_susceptible_baseline: 'Random Susceptible Baseline',
}

export const STRATEGY_DESCRIPTIONS: Readonly<Record<StrategyId, string>> = {
  ppo: 'A frozen Proximal Policy Optimization policy. It selects one antibiotic per step from those the simulator marks susceptible.',
  random_susceptible_baseline:
    'The existing baseline (implemented by the Greedy policy in the scientific code). It samples uniformly at random among susceptible antibiotics and is not a search for the best sequence.',
}

export function strategyName(strategy: StrategyId): string {
  return STRATEGY_NAMES[strategy]
}

export const GLOSSARY = {
  susceptible:
    'The antibiotic is marked susceptible in the current simulated resistance profile. This is a simulator flag, not clinical efficacy.',
  resistant: 'The antibiotic is marked resistant in the current simulated resistance profile.',
  feasible:
    "Feasible under the simulator's current action mask: only antibiotics that are susceptible in the current state may be selected.",
  transitionSupport:
    'Whether candidate transition data exist for the selected action in the current state. It is separate from susceptibility.',
  unsupported:
    'The simulator has no candidate transition for this action in this state, so it leaves the profile unchanged. This is a data gap, not evidence that the antibiotic worked.',
  supported: 'The simulator has at least one modeled transition outcome for this action in this state.',
  observedOutcome: 'What the simulator actually did after the action. It is a simulated outcome, not a clinical one.',
  resistanceEmergence:
    'A step after which the number of resistant antibiotics increased. It counts steps, not individual antibiotics.',
  noFeasibleActions:
    'Every antibiotic is resistant, so no action is feasible and the episode ends before any treatment step.',
  singleRun:
    'One run is a single stochastic sample. It does not show that either strategy is better, and it is not clinical evidence.',
  sameSeed:
    'Both strategies share the environment seed, but equal seeds do not guarantee identical random draws once their trajectories diverge.',
} as const

const OUTCOME_LABELS: Readonly<Record<string, string>> = {
  cross_resistance: 'Cross-resistance: a target drug became resistant',
  collateral_sensitivity: 'Collateral sensitivity: a target drug became susceptible',
  neutral: 'Neutral: profile unchanged',
}

export const TERMINATION_LABELS: Readonly<Record<string, string>> = {
  maximum_horizon: 'Reached the maximum horizon',
  no_effective_antibiotic: 'No susceptible antibiotic remained',
}

export function terminationLabel(reason: string): string {
  return TERMINATION_LABELS[reason] ?? reason.replaceAll('_', ' ')
}

export function outcomeLabel(step: StepTrace): string {
  if (!step.hasCandidateTransition) {
    return 'No modeled outcome: profile unchanged'
  }
  return OUTCOME_LABELS[step.transitionStatus] ?? step.transitionStatus.replaceAll('_', ' ')
}

export function transitionSupportLabel(hasCandidateTransition: boolean): string {
  return hasCandidateTransition ? 'Transition data available' : 'No supported transition data'
}

/** Humanised fallback for a server `code` that this interface has no specific wording for. */
export function humanise(code: string): string {
  const spaced = code.replaceAll('_', ' ')
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}
