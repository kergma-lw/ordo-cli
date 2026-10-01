"""compose.project probe."""

from __future__ import annotations

from connectors.compose._shared import observe_project
from ordo.plugin_sdk import OperationContext, OperationOutcome, ok, probe
from ordo.model.human import declare_human


HUMAN = declare_human({'title': 'Inspect Compose project',
 'goal': 'You need project-level runtime state before deciding whether to start, stop, or inspect one service.',
 'summary': 'Probe one Compose project as a single orchestration unit.',
 'sections': [{'heading': 'Use when',
               'items': ['A lifecycle decision concerns the project as a whole rather than one declared service.']},
               {'heading': 'What to provide',
                 'items': ['`Compose target`: context-defaulted; this operation accepts no operation-local target, so it uses the Compose directory, file, and project name selected by the workflow\'s playbook or profile settings. To inspect a different project, select settings with different Compose values; this operation has no per-call override.']},
              {'heading': 'Result and boundary',
                'items': ['Later steps can use `project`, `declared_services` (the declared services), `state`, `service_counts`, and `services` from the '
                          'per-service snapshot.',
                         'This is an observation, not a lock: another process can change Compose state after it is read. '
                          'It fails when the project cannot be inspected or the orchestration tool is unavailable.']},
              {'heading': 'Do not use for',
               'items': ['Service-specific health or container details; use connector.compose.service for that '
                         'narrower observation.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.compose', 'summary': 'Parent Compose connector family'},
                              {'handle': 'connector.compose.service',
                               'summary': 'Sibling probe for one declared service'},
                              {'handle': 'connector.compose.start',
                               'summary': 'Lifecycle action that commonly follows a project-level observation'}]},
              {'heading': 'Examples', 'items': ['compose.project with inputs {}']},
              {'heading': 'Inspect next',
               'items': ['connector.compose.service', 'connector.compose.start', 'operations']}]})

def info():
    return probe(
        name="project",
        human=HUMAN,
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
