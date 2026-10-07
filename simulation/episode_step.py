from dataclasses import dataclass
import random

from simulation.action_space import ActionSpace
from simulation.observation import Observation
from simulation.resistance_state import ANTIBIOTICS, ResistanceState
from simulation.reward import RewardFunction
from simulation.stochastic_transition_model import (
    SampledTransition,
    StochasticTransitionModel,
)
from simulation.treatment_action import TreatmentActionResult
from simulation.treatment_action_executor import TreatmentActionExecutor


@dataclass(frozen=True)
class EpisodeStepResult:
    previous_state: ResistanceState
    next_state: ResistanceState
    treatment: TreatmentActionResult
    sampled_transition: SampledTransition
    reward: float
    observation: Observation


class EpisodeStep:
    def __init__(
        self,
        treatment_executor: TreatmentActionExecutor | None = None,
        transition_model: StochasticTransitionModel | None = None,
        reward_function: RewardFunction | None = None,
        action_space: ActionSpace | None = None,
    ):
        self.treatment_executor = (
            treatment_executor or TreatmentActionExecutor()
        )
        self.transition_model = (
            transition_model or StochasticTransitionModel()
        )
        self.reward_function = (
            reward_function or RewardFunction()
        )
        self.action_space = action_space or ActionSpace()

    def execute(
        self,
        state: ResistanceState,
        action: int,
        treatment_step: int,
        horizon: int | None = None,
        seed: int | None = None,
        rng: random.Random | None = None,
    ) -> EpisodeStepResult:
        if seed is not None and rng is not None:
            raise ValueError(
                "Provide either seed or rng, not both."
            )

        treatment = self.treatment_executor.execute(
            state,
            action,
        )

        next_state, sampled_transition = self.transition_model.step(
            state,
            action,
            seed=seed,
            rng=rng,
        )

        reward = self.reward_function.calculate(
            next_state,
            remaining_horizon_steps=(
                0 if horizon is None else max(0, horizon - treatment_step - 1)
            ),
        )

        observation = self._build_observation(
            state=next_state,
            action=action,
            treatment_step=treatment_step + 1,
        )

        return EpisodeStepResult(
            previous_state=state,
            next_state=next_state,
            treatment=treatment,
            sampled_transition=sampled_transition,
            reward=reward,
            observation=observation,
        )

    @staticmethod
    def _build_observation(
        state: ResistanceState,
        action: int,
        treatment_step: int,
    ) -> Observation:
        susceptibility = state.resistance

        last_action = tuple(
            1 if index == action else 0
            for index in range(len(ANTIBIOTICS))
        )

        return Observation(
            susceptibility=susceptibility,
            last_action=last_action,
            treatment_step=treatment_step,
        )