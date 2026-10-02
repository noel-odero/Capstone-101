from dataclasses import dataclass
import random

from simulation.candidate_transition import CandidateTransition


REFERENCE_SCENARIO_ID = "REF_UNIFORM_SUPPORTED"
SENSITIVITY_SCENARIOS = {
    "SENSITIVITY_Q_000": 0.0,
    "SENSITIVITY_Q_025": 0.25,
    "SENSITIVITY_Q_050": 0.5,
    "SENSITIVITY_Q_075": 0.75,
    "SENSITIVITY_Q_100": 1.0,
}
RESISTANCE_CHANGING_OUTCOMES = {
    "cross_resistance",
    "collateral_sensitivity",
}


@dataclass(frozen=True)
class SampledTransition:
    candidate: CandidateTransition | None
    probability: float | None
    scenario_id: str
    candidates: tuple[CandidateTransition, ...]
    status: str
    candidate_probabilities: tuple[float, ...]
    no_transition_probability: float | None
    occurrence_probability: float
    seed: int | None


class TransitionSampler:
    def __init__(self, scenario_id: str = REFERENCE_SCENARIO_ID):
        if (
            scenario_id != REFERENCE_SCENARIO_ID
            and scenario_id not in SENSITIVITY_SCENARIOS
        ):
            raise ValueError(f"Unknown transition scenario: {scenario_id}")

        self.scenario_id = scenario_id

    def sample(
        self,
        candidates: tuple[CandidateTransition, ...],
        seed: int | None = None,
        rng: random.Random | None = None,
    ) -> SampledTransition:
        if seed is not None and rng is not None:
            raise ValueError(
                "Provide either seed or rng, not both."
            )

        unique_candidates = self._deduplicate(candidates)
        if rng is None:
            rng = random.Random(seed)

        if not unique_candidates:
            return SampledTransition(
                candidate=None,
                probability=None,
                scenario_id=self.scenario_id,
                candidates=(),
                status="unsupported_no_candidate",
                candidate_probabilities=(),
                no_transition_probability=None,
                occurrence_probability=self.occurrence_probability,
                seed=seed,
            )

        if self.scenario_id == REFERENCE_SCENARIO_ID:
            probabilities = tuple(
                1.0 / len(unique_candidates)
                for _ in unique_candidates
            )
            selected_candidate = rng.choice(unique_candidates)
            return SampledTransition(
                candidate=selected_candidate,
                probability=1.0 / len(unique_candidates),
                scenario_id=self.scenario_id,
                candidates=unique_candidates,
                status=selected_candidate.outcome,
                candidate_probabilities=probabilities,
                no_transition_probability=0.0,
                occurrence_probability=1.0,
                seed=seed,
            )

        resistance_candidates = tuple(
            candidate
            for candidate in unique_candidates
            if candidate.outcome in RESISTANCE_CHANGING_OUTCOMES
        )

        if not resistance_candidates:
            selected_candidate = rng.choice(unique_candidates)
            probability = 1.0 / len(unique_candidates)
            return SampledTransition(
                candidate=selected_candidate,
                probability=probability,
                scenario_id=self.scenario_id,
                candidates=unique_candidates,
                status=selected_candidate.outcome,
                candidate_probabilities=tuple(
                    probability for _ in unique_candidates
                ),
                no_transition_probability=0.0,
                occurrence_probability=self.occurrence_probability,
                seed=seed,
            )

        occurrence_probability = self.occurrence_probability
        candidate_probability = (
            occurrence_probability / len(resistance_candidates)
        )
        probabilities = tuple(
            candidate_probability
            if candidate in resistance_candidates
            else 0.0
            for candidate in unique_candidates
        )
        no_transition_probability = 1.0 - occurrence_probability

        if rng.random() >= occurrence_probability:
            return SampledTransition(
                candidate=None,
                probability=None,
                scenario_id=self.scenario_id,
                candidates=unique_candidates,
                status="no_transition",
                candidate_probabilities=probabilities,
                no_transition_probability=no_transition_probability,
                occurrence_probability=occurrence_probability,
                seed=seed,
            )

        selected_candidate = rng.choice(resistance_candidates)

        return SampledTransition(
            candidate=selected_candidate,
            probability=candidate_probability,
            scenario_id=self.scenario_id,
            candidates=unique_candidates,
            status=selected_candidate.outcome,
            candidate_probabilities=probabilities,
            no_transition_probability=no_transition_probability,
            occurrence_probability=occurrence_probability,
            seed=seed,
        )

    @property
    def occurrence_probability(self) -> float:
        if self.scenario_id == REFERENCE_SCENARIO_ID:
            return 1.0
        return SENSITIVITY_SCENARIOS[self.scenario_id]

    @staticmethod
    def _deduplicate(
        candidates: tuple[CandidateTransition, ...],
    ) -> tuple[CandidateTransition, ...]:
        grouped: dict[
            tuple[str, str],
            set[str],
        ] = {}

        for candidate in candidates:
            key = (
                candidate.target_drug,
                candidate.outcome,
            )

            if key not in grouped:
                grouped[key] = set()

            grouped[key].update(candidate.source_ids)

        deduplicated = tuple(
            CandidateTransition(
                target_drug=target_drug,
                outcome=outcome,
                source_ids=tuple(sorted(source_ids)),
            )
            for (target_drug, outcome), source_ids
            in grouped.items()
        )

        return deduplicated