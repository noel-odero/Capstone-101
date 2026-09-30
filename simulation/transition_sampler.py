from dataclasses import dataclass
import random

from simulation.candidate_transition import CandidateTransition


REFERENCE_SCENARIO_ID = "REF_UNIFORM_SUPPORTED"


@dataclass(frozen=True)
class SampledTransition:
    candidate: CandidateTransition
    probability: float
    scenario_id: str
    candidates: tuple[CandidateTransition, ...]


class TransitionSampler:
    def sample(
        self,
        candidates: tuple[CandidateTransition, ...],
        seed: int | None = None,
        rng: random.Random | None = None,
    ) -> SampledTransition:
        if not candidates:
            raise ValueError(
                "Cannot sample from an empty candidate set."
            )

        if seed is not None and rng is not None:
            raise ValueError(
                "Provide either seed or rng, not both."
            )

        unique_candidates = self._deduplicate(candidates)

        probability = 1.0 / len(unique_candidates)

        if rng is None:
            rng = random.Random(seed)

        selected_candidate = rng.choice(unique_candidates)

        return SampledTransition(
            candidate=selected_candidate,
            probability=probability,
            scenario_id=REFERENCE_SCENARIO_ID,
            candidates=unique_candidates,
        )

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