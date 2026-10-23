"""FastAPI application: thin routes over service.runtime and service.rollout.

Run from the repository root: python -m uvicorn service.main:app --workers 1
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
import logging
from pathlib import Path
import uuid

from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ml.src.ppo_inference import InferenceError
from service import __version__, rollout
from service.errors import ModelNotReadyError, ServiceError, to_service_error
from service.runtime import ModelRuntime, load_runtime
from service.schemas import (
    AntibioticsResponse,
    CompareRequest,
    ComparisonResponse,
    ErrorResponse,
    HealthResponse,
    ModelResponse,
    ProfileRequest,
    ProfileValidationResponse,
    RecommendationResponse,
    RecommendRequest,
    SimulateRequest,
    SimulationResponse,
)

logger = logging.getLogger("service")

ERROR_RESPONSES = {
    422: {"model": ErrorResponse, "description": "Invalid request or inference context."},
    500: {"model": ErrorResponse, "description": "Unexpected internal failure (see request_id in server logs)."},
    503: {"model": ErrorResponse, "description": "Frozen model or data unavailable or failed verification."},
}


@dataclass
class RuntimeState:
    runtime: ModelRuntime | None = None
    error_code: str | None = "model_not_loaded"
    error_message: str = "The frozen model has not been loaded."


def _request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if request_id is None:
        request_id = request.state.request_id = str(uuid.uuid4())
    return request_id


def _error_response(request: Request, error: ServiceError) -> JSONResponse:
    request_id = _request_id(request)
    body = {"code": error.code, "message": error.message, "request_id": request_id}
    if error.details is not None:
        body["details"] = error.details
    return JSONResponse(
        status_code=error.status_code, content={"error": body}, headers={"X-Request-ID": request_id}
    )


def _load_state(manifest_path: Path | None) -> RuntimeState:
    try:
        return RuntimeState(
            runtime=load_runtime(manifest_path) if manifest_path else load_runtime(),
            error_code=None,
            error_message="",
        )
    except Exception as error:
        logger.exception("Frozen model failed to load or verify.")
        safe = to_service_error(error)
        return RuntimeState(runtime=None, error_code=safe.code, error_message=safe.message)


def create_app(manifest_path: str | Path | None = None) -> FastAPI:
    manifest = Path(manifest_path) if manifest_path else None

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.runtime_state = _load_state(manifest)
        yield

    app = FastAPI(
        title="Antibiotic stewardship simulation service (internal)",
        version=__version__,
        description="Internal API over frozen PPO/DQN policies and the stochastic resistance simulator. "
        "Simulation output only; not clinical advice.",
        lifespan=lifespan,
    )
    app.state.runtime_state = RuntimeState()

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = _request_id(request)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(ServiceError)
    async def handle_service_error(request: Request, error: ServiceError):
        if error.status_code >= 500:
            logger.error("Service error %s (request %s)", error.code, _request_id(request), exc_info=error)
        return _error_response(request, error)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, error: RequestValidationError):
        details = [
            {"loc": list(item["loc"]), "message": item["msg"], "type": item["type"]}
            for item in error.errors()
        ]
        return _error_response(
            request,
            ServiceError(
                "The request body failed validation.",
                code="request_validation_error",
                status_code=422,
                details=details,
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, error: StarletteHTTPException):
        return _error_response(
            request,
            ServiceError(str(error.detail), code="http_error", status_code=error.status_code),
        )

    async def handle_known_failure(request: Request, error: Exception):
        safe = to_service_error(error)
        if safe.status_code >= 500:
            logger.error(
                "Mapped %s to %s (request %s)", type(error).__name__, safe.code, _request_id(request), exc_info=error
            )
        else:
            logger.info("Rejected request %s: %s", _request_id(request), safe.code)
        return _error_response(request, safe)

    app.add_exception_handler(InferenceError, handle_known_failure)
    app.add_exception_handler(OSError, handle_known_failure)
    app.add_exception_handler(Exception, handle_known_failure)

    def require_runtime(request: Request) -> ModelRuntime:
        state: RuntimeState = request.app.state.runtime_state
        if state.runtime is None:
            raise ModelNotReadyError(state.error_message, code=state.error_code)
        return state.runtime

    @app.get("/internal/health", response_model=HealthResponse, responses={503: ERROR_RESPONSES[503]})
    def health(request: Request, response: Response) -> dict:
        state: RuntimeState = request.app.state.runtime_state
        if state.runtime is None:
            response.status_code = 503
            return {
                "status": "unavailable",
                "model_ready": False,
                "service_version": __version__,
                "error_code": state.error_code,
                "message": state.error_message,
            }
        return {
            "status": "ok",
            "model_ready": True,
            "service_version": __version__,
            "model_id": state.runtime.engine.model_id,
            "checkpoint_sha256": state.runtime.engine.checkpoint_sha256,
            "message": "The frozen model passed checkpoint, data and contract verification.",
        }

    @app.get("/internal/model", response_model=ModelResponse, responses=ERROR_RESPONSES)
    def model(runtime: ModelRuntime = Depends(require_runtime)) -> dict:
        return runtime.describe_model()

    @app.get("/internal/antibiotics", response_model=AntibioticsResponse, responses=ERROR_RESPONSES)
    def antibiotics(runtime: ModelRuntime = Depends(require_runtime)) -> dict:
        return runtime.list_antibiotics()

    @app.post("/internal/profiles/validate", response_model=ProfileValidationResponse, responses=ERROR_RESPONSES)
    def validate_profile(body: ProfileRequest, runtime: ModelRuntime = Depends(require_runtime)) -> dict:
        return runtime.validate_profile(body.resistance_profile)

    @app.post("/internal/recommend", response_model=RecommendationResponse, responses=ERROR_RESPONSES)
    def recommend(body: RecommendRequest, runtime: ModelRuntime = Depends(require_runtime)) -> dict:
        return runtime.recommend(body.resistance_profile, body.last_action, body.treatment_step)

    @app.post("/internal/simulate", response_model=SimulationResponse, responses=ERROR_RESPONSES)
    def simulate(body: SimulateRequest, runtime: ModelRuntime = Depends(require_runtime)) -> dict:
        return rollout.simulate(
            runtime,
            strategy=body.strategy,
            resistance_profile=body.resistance_profile,
            environment_seed=body.environment_seed,
            policy_seed=body.policy_seed,
        )

    @app.post("/internal/compare", response_model=ComparisonResponse, responses=ERROR_RESPONSES)
    def compare(body: CompareRequest, runtime: ModelRuntime = Depends(require_runtime)) -> dict:
        return rollout.compare(
            runtime,
            resistance_profile=body.resistance_profile,
            environment_seed=body.environment_seed,
            policy_seed=body.policy_seed,
        )

    return app


app = create_app()
