"""compose.project probe."""

from __future__ import annotations

from connectors.compose._shared import observe_project
from ordo.plugin_sdk import OperationContext, OperationOutcome, ok, probe


def info():
    return probe(
        name="project",
        summary="Observe one Compose project as an orchestration unit.",
        outputs={
            "project": "string",
            "declared_services": "array[string]",
            "state": "string",
            "service_counts": "object",
            "services": "object",
        },
        failure_modes=("project_invalid", "orchestrator_unavailable", "observation_failed"),
        examples=(({"reference": "compose.project", "inputs": {}},)),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    observation = observe_project(ctx)
    if isinstance(observation, OperationOutcome):
        return observation
    return ok(
        summary=f"Compose project is {observation.state}",
        outputs=observation.to_outputs(),
    )
