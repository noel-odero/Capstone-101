"""Service error types and the single mapping from internal exceptions to safe API errors.

Messages returned to callers are fixed or come from validation of the caller's own input; exception
text (which can contain file paths) is only ever logged.
"""
from __future__ import annotations

from typing import Any

from ml.src.ppo_inference import (
    CheckpointIntegrityError,
    ContractMismatchError,
    EmptyActionMaskError,
    InferenceError,
    InfeasibleActionError,
    InvalidContextError,
)


class ServiceError(Exception):
    status_code = 500
    code = "internal_error"
    message = "The service could not complete the request."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: list[dict[str, Any]] | None = None,
    ):
        super().__init__(message or self.message)
        self.message = message or self.message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.details = details


class InvalidRequestError(ServiceError):
    status_code = 422
    code = "invalid_request"
    message = "The request is invalid."


class ModelNotReadyError(ServiceError):
    status_code = 503
    code = "model_not_ready"
    message = "The frozen model is not ready."


class ComparisonContractError(ServiceError):
    status_code = 500
    code = "comparison_contract_violation"
    message = "The paired runs did not satisfy the comparison contract; no result was returned."

    def __init__(self, check: str):
        super().__init__(details=[{"check": check}])


def to_service_error(error: BaseException) -> ServiceError:
    """Map any exception to a safe ServiceError; callers must log the original separately."""
    if isinstance(error, ServiceError):
        return error
    if isinstance(error, InvalidContextError):
        return InvalidRequestError(str(error), code="invalid_context")
    if isinstance(error, CheckpointIntegrityError):
        return ServiceError(
            "Checkpoint integrity verification failed.",
            code="checkpoint_integrity_failure",
            status_code=503,
        )
    if isinstance(error, ContractMismatchError):
        return ServiceError(
            "The model, simulator data and manifest do not agree.",
            code="model_contract_mismatch",
            status_code=503,
        )
    if isinstance(error, EmptyActionMaskError):
        return ServiceError(
            "A non-terminal state had no feasible action.", code="empty_action_mask", status_code=500
        )
    if isinstance(error, InfeasibleActionError):
        return ServiceError(
            "The policy selected an action outside the feasibility mask; the run was aborted.",
            code="infeasible_policy_action",
            status_code=500,
        )
    if isinstance(error, InferenceError):
        return ServiceError("Inference failed.", code="inference_failure", status_code=500)
    if isinstance(error, OSError):
        return ServiceError(
            "A required model or transition data file is unavailable.",
            code="model_or_data_unavailable",
            status_code=503,
        )
    return ServiceError()
