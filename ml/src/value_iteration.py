from dataclasses import dataclass
import math
from numbers import Real

from simulation.deterministic_reference import DeterministicReferenceEnvironment
from simulation.episode import EpisodeState


@dataclass
class ValueIterationResult:
    """Finite-horizon planning tables keyed by EpisodeState.

    action_values[state][action] is the optimal return after that first action.
    Infeasible actions have value negative infinity.
    Terminal states have zero state/action values and policy action None.
    These tables describe only the supplied computational reference problem.
    """

    state_values: dict[EpisodeState, float]
    action_values: dict[EpisodeState, dict[int, float]]
    policy: dict[EpisodeState, int | None]
    gamma: float


def value_iteration(
    environment: DeterministicReferenceEnvironment,
    gamma: float = 1.0,
) -> ValueIterationResult:
    """Solve the known finite-horizon model using reverse-time Bellman backups.

    gamma must be a finite real number in [0, 1]; booleans are not accepted.
    Exact maximizing ties select the lowest action ID, without a tolerance.
    Only pure planning methods are used; no reset, step, episode, or RNG access.
    """
    if isinstance(gamma, bool) or not isinstance(gamma, Real):
        raise TypeError("Discount factor must be a real number.")
    gamma = float(gamma)
    if not math.isfinite(gamma) or not 0.0 <= gamma <= 1.0:
        raise ValueError("Discount factor must be finite and between 0 and 1.")
    if gamma != 1.0:
        raise ValueError("Normalized resistance burden planning requires gamma=1.")

    states = sorted(
        environment.states(),
        key=lambda state: state.treatment_step,
        reverse=True,
    )
    actions = range(
        int(environment.action_space.start),
        int(environment.action_space.start + environment.action_space.n),
    )
    state_values: dict[EpisodeState, float] = {}
    action_values: dict[EpisodeState, dict[int, float]] = {}
    policy: dict[EpisodeState, int | None] = {}

    for state in states:
        if environment.is_terminal(state):
            state_values[state] = (
                -float(environment.max_steps - state.treatment_step)
                if all(state.resistance_state.resistance)
                else 0.0
            )
            action_values[state] = {action: 0.0 for action in actions}
            policy[state] = None
            continue

        values = {action: -math.inf for action in actions}
        feasible_actions = environment.feasible_actions(state)
        if not feasible_actions:
            raise RuntimeError("A nonterminal state has no feasible action.")
        for action in feasible_actions:
            next_state, reward, terminal, _ = environment.transition(state, action)
            continuation = 0.0 if terminal else state_values[next_state]
            values[action] = reward + gamma * continuation

        best_action = max(feasible_actions, key=lambda action: values[action])
        action_values[state] = values
        state_values[state] = values[best_action]
        policy[state] = best_action

    return ValueIterationResult(state_values, action_values, policy, gamma)