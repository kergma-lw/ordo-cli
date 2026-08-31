"""compose.start action."""

from __future__ import annotations

import time

from connectors.compose._shared import compose_command, map_start_failure, observe_project, observe_service
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, action, fail_with_diagnostic, ok, preflight_observation


_START_FAILURE_GRACE_SECONDS = 5


def info():
    return action(
        name="start",
        summary="Bring one Compose project or service into operational running state.",
        inputs={"service": "string | null"},
        effects=("bring the requested Compose target into operational running state",),
        outputs={
            "target_kind": "string",
            "target": "string",
            "state": "string",
            "changed": "boolean",
            "changed_services": "array[string]",
        },
        failure_modes=(
            "service_not_declared",
            "project_invalid",
            "orchestrator_unavailable",
            "image_unavailable",
            "build_failed",
            "dependency_failed",
            "runtime_start_failed",
            "healthcheck_failed",
            "start_failed",
        ),
        invalidates_observations=("compose.*",),
        preflight_observations=(preflight_observation(probe="compose.project"),),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    service = _optional_service(ctx)
    if isinstance(service, OperationOutcome):
        return service

    before = observe_service(ctx, service) if service is not None else observe_project(ctx)
    if isinstance(before, OperationOutcome):
        return before

    if service is None and before.state == "running":
        return ok(summary="Compose project is already running", outputs={"target_kind": "project", "state": "running", "changed": False})
    if service is not None and before.state == "running":
        return ok(summary=f"Compose service '{service}' is already running", outputs={"target_kind": "service", "target": service, "state": "running", "changed": False})

    argv = compose_command(ctx, "up", "-d", *( [service] if service is not None else [] ))
    try:
        command = ctx.command(argv, failures={"os_error": "start_failed", "nonzero": "start_failed"})
    except MappedOutcomeError as exc:
        recovered = _recover_from_start_failure(ctx, exc, service=service)
        if recovered is not None:
            return recovered
        return map_start_failure(ctx, exc, service=service)

    after = observe_service(ctx, service) if service is not None else observe_project(ctx)
    if isinstance(after, OperationOutcome):
        return fail_with_diagnostic(
            code="start_failed",
            summary="Compose target start completed but follow-up observation failed",
            diagnostic_code="action.compose_start.post_observation_failed",
            reference=ctx.reference,
            raw=command.raw,
        )

    state = after.state if service is None else after.state
    if state == "running":
        outputs = {"target_kind": "project", "state": "running", "changed": True} if service is None else {"target_kind": "service", "target": service, "state": "running", "changed": True}
        return ok(summary="Compose project started" if service is None else f"Compose service '{service}' started", outputs=outputs, raw=command.raw)
    if state in {"starting", "degraded"}:
        outputs = {"target_kind": "project", "state": "degraded", "changed": True} if service is None else {"target_kind": "service", "target": service, "state": "degraded", "changed": True}
        return ok(summary="Compose project is only partially operational after start" if service is None else f"Compose service '{service}' is only partially operational after start", outputs=outputs, raw=command.raw)
    outputs = {"target_kind": "project", "state": "failed", "changed": True} if service is None else {"target_kind": "service", "target": service, "state": "failed", "changed": True}
    return fail_with_diagnostic(
        code="start_failed",
        summary="Compose project did not reach running state" if service is None else f"Compose service '{service}' did not reach running state",
        diagnostic_code="action.compose_start.failed_state",
        reference=ctx.reference,
        outputs=outputs,
        raw=command.raw,
    )


def _recover_from_start_failure(
    ctx: OperationContext,
    exc: MappedOutcomeError,
    *,
    service: str | None,
) -> OperationOutcome | None:
    time.sleep(_START_FAILURE_GRACE_SECONDS)
    after = observe_service(ctx, service) if service is not None else observe_project(ctx)
    if isinstance(after, OperationOutcome):
        return None

    state = after.state
    if state not in {"running", "starting", "degraded"}:
        return None

    summary = "Compose project started" if service is None else f"Compose service '{service}' started"
    if state in {"starting", "degraded"}:
        summary = (
            "Compose project is only partially operational after start"
            if service is None
            else f"Compose service '{service}' is only partially operational after start"
        )
    outputs = {"target_kind": "project", "state": state, "changed": True} if service is None else {"target_kind": "service", "target": service, "state": state, "changed": True}
    return OperationOutcome(
        status="ok",
        summary=summary,
        outputs=outputs,
        diagnostics=(
            Diagnostic(
                code="action.compose_start.recovered_after_nonzero",
                level="warning",
                message="Compose start command returned nonzero but the target became operational during the recovery window",
                details={
                    "reference": ctx.reference,
                    "service": service,
                    "state": state,
                    "grace_seconds": _START_FAILURE_GRACE_SECONDS,
                },
            ),
        ),
        raw=dict(exc.outcome.raw),
    )


def _optional_service(ctx: OperationContext) -> str | None | OperationOutcome:
    try:
        value = ctx.input("service")
    except MappedOutcomeError as exc:
        if exc.outcome.status == "input_error":
            return None
        return exc.outcome
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return fail_with_diagnostic(
            code="start_failed",
            summary="Compose start requires service to be a non-empty string when provided",
            diagnostic_code="action.compose_start.service_invalid",
            reference=ctx.reference,
            details={"service": value},
        )
    return value
