"""compose.remove action."""

from __future__ import annotations

from connectors.compose._shared import compose_command, map_remove_failure, observe_service
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, fail_with_diagnostic, ok, preflight_observation


def info():
    return action(
        name="remove",
        summary="Remove one stopped materialized Compose service instance.",
        inputs={"service": "string"},
        effects=("remove the materialized runtime instance for one Compose service",),
        outputs={
            "target_kind": "string",
            "target": "string",
            "state": "string",
            "changed": "boolean",
        },
        failure_modes=(
            "service_not_declared",
            "service_running",
            "project_invalid",
            "orchestrator_unavailable",
            "runtime_remove_failed",
            "remove_failed",
        ),
        invalidates_observations=("compose.*",),
        preflight_observations=(preflight_observation(probe="compose.service", with_={"service": "{service}"}),),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    raw_service = ctx.input("service")
    if not isinstance(raw_service, str) or not raw_service.strip():
        return fail_with_diagnostic(
            code="remove_failed",
            summary="Compose remove requires a non-empty service name",
            diagnostic_code="action.compose_remove.service_invalid",
            reference=ctx.reference,
            details={"service": raw_service},
        )
    service = raw_service.strip()

    before = observe_service(ctx, service)
    if isinstance(before, OperationOutcome):
        return before
    if before.state == "absent":
        return ok(
            summary=f"Compose service '{service}' is already absent",
            outputs={"target_kind": "service", "target": service, "state": "absent", "changed": False},
        )
    if before.state in {"running", "starting", "degraded"}:
        return fail_with_diagnostic(
            code="service_running",
            summary=f"Compose service '{service}' is still running and must be stopped before removal",
            diagnostic_code="action.compose_remove.service_running",
            reference=ctx.reference,
            details={"service": service, "state": before.state},
            outputs={"target_kind": "service", "target": service, "state": "failed", "changed": False},
        )

    try:
        command = ctx.command(
            compose_command(ctx, "rm", "-f", service),
            failures={"os_error": "remove_failed", "nonzero": "remove_failed"},
        )
    except MappedOutcomeError as exc:
        return map_remove_failure(ctx, exc, service=service)

    after = observe_service(ctx, service)
    if isinstance(after, OperationOutcome):
        return fail_with_diagnostic(
            code="remove_failed",
            summary="Compose service removal completed but follow-up observation failed",
            diagnostic_code="action.compose_remove.post_observation_failed",
            reference=ctx.reference,
            raw=command.raw,
        )

    if after.state == "absent":
        return ok(
            summary=f"Compose service '{service}' removed",
            outputs={"target_kind": "service", "target": service, "state": "absent", "changed": True},
            raw=command.raw,
        )
    if after.state == "stopped":
        return ok(
            summary=f"Compose service '{service}' was only partially removed",
            outputs={"target_kind": "service", "target": service, "state": "degraded", "changed": True},
            raw=command.raw,
        )
    return fail_with_diagnostic(
        code="remove_failed",
        summary=f"Compose service '{service}' did not reach absent state",
        diagnostic_code="action.compose_remove.failed_state",
        reference=ctx.reference,
        outputs={"target_kind": "service", "target": service, "state": "failed", "changed": True},
        raw=command.raw,
    )
