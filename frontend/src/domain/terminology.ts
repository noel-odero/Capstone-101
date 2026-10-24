import type { StrategyId } from './types'

/**
 * Every user-facing scientific label lives here so no page can describe the same thing in different words.
 * The three concepts below are kept apart on purpose: what the policy selected, whether the simulator has
 * transition data for it, and what the simulator then did.
 */

export const APP_NAME = 'AMR Decision Support'
export const APP_TAGLINE = 'An AI-powered antibiotic strategy evaluation platform.'
export const PROTOTYPE_STATEMENT =
  'Research prototype. Findings are model-derived and are not clinical treatment recommendations.'

export const PAGE_TITLES = {
  workspace: 'Home',
  evaluation: 'Strategy Evaluation',
  results: 'Analysis Results',
  trajectory: 'Resistance Trajectory',
  history: 'Analysis History',
  insights: 'Analysis Insights',
} as const

export const STRATEGY_NAMES: Readonly<Record<StrategyId, string>> = {
  ppo: 'PPO',
  dqn: 'DQN',
  random_susceptible_baseline: 'Random Susceptible Baseline',
}

export const STRATEGY_DESCRIPTIONS: Readonly<Record<StrategyId, string>> = {
  ppo: 'A frozen Proximal Policy Optimization policy. It selects one antibiotic per step from those the model marks susceptible.',
  dqn: 'A frozen Deep Q-Network policy. It selects one antibiotic per step from those the model marks susceptible.',
  random_susceptible_baseline:
    'The existing baseline (implemented by the Greedy policy in the scientific code). It samples uniformly at random among susceptible antibiotics and is not a search for the best sequence.',
}

export const GLOSSARY = {
  susceptible:
    'The antibiotic is marked susceptible in the current resistance profile. This is a model flag, not clinical efficacy.',
  resistant: 'The antibiotic is marked resistant in the current resistance profile.',
  feasible:
    "Feasible under the model's current action mask: only antibiotics that are susceptible in the current state may be selected.",
  transitionSupport:
    'Whether candidate transition data exist for the selected action in the current state. It is separate from susceptibility.',
  unsupported:
    'No modeled transition applies to this action in this state. The model keeps the profile unchanged; this does not establish biological stability or treatment effectiveness.',
  supported: 'The model has at least one transition outcome for this action in this state.',
  observedOutcome:
    'The outcome sampled by the evaluation model after an action. It is model-derived, not a measured clinical outcome.',
  resistanceEmergence:
    'A step after which the number of resistant antibiotics increased. It counts steps, not individual antibiotics.',
  noFeasibleActions:
    'Every antibiotic is resistant, so no action is feasible and the episode ends before any treatment step.',
  singleRun:
    'One run is a single stochastic sample. It does not show that either strategy is better, and it is not clinical evidence.',
  sameSeed:
    'Strategies share the environment seed. Different actions and states can produce different transition outcomes.',
} as const

export const STRATEGY_COLORS: Readonly<Record<StrategyId, string>> = {
  ppo: 'var(--color-series-ppo)',
  dqn: 'var(--color-series-dqn)',
  random_susceptible_baseline: 'var(--color-series-baseline)',
}

export function strategyLabel(strategy: StrategyId): string {
  return strategy === 'random_susceptible_baseline' ? 'Random baseline' : STRATEGY_NAMES[strategy]
}

export const TERMINATION_LABELS: Readonly<Record<string, string>> = {
  maximum_horizon: 'Reached the maximum horizon',
  no_effective_antibiotic: 'No susceptible antibiotic remained',
}

export function terminationLabel(reason: string): string {
  return TERMINATION_LABELS[reason] ?? reason.replaceAll('_', ' ')
}

/** Humanised fallback for a server `code` that this interface has no specific wording for. */
export function humanise(code: string): string {
  const spaced = code.replaceAll('_', ' ')
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}
