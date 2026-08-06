"""compose.service probe."""

from __future__ import annotations

from connectors.compose._shared import observe_service
from ordo.plugin_sdk import OperationContext, OperationOutcome, fail_with_diagnostic, ok, probe


def info():
    return probe(
        name="service",
        summary="Observe one declared Compose service as an orchestration unit.",
        inputs={"service": "string"},
        outputs={
            "service": "string",
            "declared": "boolean",
            "state": "string",
            "healthy": "boolean | null",
            "containers": "object",
            "published_ports": "array[string]",
        },
        failure_modes=("service_not_declared", "project_invalid", "orchestrator_unavailable", "observation_failed"),
        examples=(({"reference": "compose.service", "inputs": {"service": "api"}},)),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    raw_service = ctx.input("service")
    if not isinstance(raw_service, str) or not raw_service.strip():
        return fail_with_diagnostic(
            code="observation_failed",
            summary="Compose service probe requires a non-empty service name",
            diagnostic_code="probe.compose_service.service_invalid",
            reference=ctx.reference,
            details={"service": raw_service},
        )
    observation = observe_service(ctx, raw_service)
    if isinstance(observation, OperationOutcome):
        return observation
    return ok(
        summary=f"Compose service '{raw_service}' is {observation.state}",
        outputs=observation.to_outputs(),
    )
