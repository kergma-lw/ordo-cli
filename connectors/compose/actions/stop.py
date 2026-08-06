"""compose.stop action."""

from __future__ import annotations

from connectors.compose._shared import compose_command, map_stop_failure, observe_project, observe_service
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, fail_with_diagnostic, ok, preflight_observation


def info():
    return action(
        name="stop",
        summary="Stop one Compose project or service.",
        inputs={"service": "string | null"},
        effects=("stop the requested Compose target",),
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
            "dependency_stop_blocked",
            "runtime_stop_failed",
            "stop_failed",
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

    if service is None and before.state in {"stopped", "down"}:
        return ok(summary="Compose project is already stopped", outputs={"target_kind": "project", "state": "stopped", "changed": False})
    if service is not None and before.state in {"stopped", "absent"}:
        return ok(summary=f"Compose service '{service}' is already stopped", outputs={"target_kind": "service", "target": service, "state": "stopped", "changed": False})

    argv = compose_command(ctx, "stop", *( [service] if service is not None else [] ))
    try:
        command = ctx.command(argv, failures={"os_error": "stop_failed", "nonzero": "stop_failed"})
    except MappedOutcomeError as exc:
        return map_stop_failure(ctx, exc, service=service)

    after = observe_service(ctx, service) if service is not None else observe_project(ctx)
    if isinstance(after, OperationOutcome):
        return fail_with_diagnostic(
            code="stop_failed",
            summary="Compose target stop completed but follow-up observation failed",
            diagnostic_code="action.compose_stop.post_observation_failed",
            reference=ctx.reference,
            raw=command.raw,
        )

    final_state = after.state
    if service is None and final_state in {"stopped", "down"}:
        return ok(summary="Compose project stopped", outputs={"target_kind": "project", "state": "stopped", "changed": True}, raw=command.raw)
    if service is not None and final_state in {"stopped", "absent"}:
        return ok(summary=f"Compose service '{service}' stopped", outputs={"target_kind": "service", "target": service, "state": "stopped", "changed": True}, raw=command.raw)
    if final_state in {"starting", "degraded", "running"}:
        outputs = {"target_kind": "project", "state": "degraded", "changed": True} if service is None else {"target_kind": "service", "target": service, "state": "degraded", "changed": True}
        return ok(summary="Compose project only partially stopped" if service is None else f"Compose service '{service}' only partially stopped", outputs=outputs, raw=command.raw)
    outputs = {"target_kind": "project", "state": "failed", "changed": True} if service is None else {"target_kind": "service", "target": service, "state": "failed", "changed": True}
    return fail_with_diagnostic(
        code="stop_failed",
        summary="Compose project did not reach stopped state" if service is None else f"Compose service '{service}' did not reach stopped state",
        diagnostic_code="action.compose_stop.failed_state",
        reference=ctx.reference,
        outputs=outputs,
        raw=command.raw,
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
            code="stop_failed",
            summary="Compose stop requires service to be a non-empty string when provided",
            diagnostic_code="action.compose_stop.service_invalid",
            reference=ctx.reference,
            details={"service": value},
        )
    return value
