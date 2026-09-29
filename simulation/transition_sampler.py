from dataclasses import dataclass

from simulation.candidate_transition import CandidateTransition


@dataclass(frozen=True)
class SampledTransition:
    candidate: CandidateTransition

class TransitionSampler:
    def sample(
        self,
        candidates: tuple[CandidateTransition, ...],
        seed: int | None = None,
    ) -> SampledTransition:
        if not candidates:
            raise ValueError(
                "Cannot sample from an empty candidate set."
            )

        if len(candidates) > 1:
            raise ValueError(
                "Stochastic probabilities are unresolved for multiple "
                "candidate transitions."
            )

        return SampledTransition(
            candidate=candidates[0],
        )