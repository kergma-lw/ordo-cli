"""compose.service probe."""

from __future__ import annotations

from connectors.compose._shared import observe_service
from ordo.plugin_sdk import OperationContext, OperationOutcome, fail_with_diagnostic, ok, probe
from ordo.model.human import declare_human


HUMAN = declare_human({'title': 'Compose service',
 'goal': 'Decide whether one named Compose service is ready for the next lifecycle action.',
 'summary': 'Probe one declared Compose service as a single orchestration unit.',
 'sections': [{'heading': 'Use when',
                'items': ['A later decision needs the current status of one named service, such as whether it is absent, starting, running, stopped, or degraded.',
                          'You need to distinguish a declared service that has no current container from a service with observed running or unhealthy containers.']},
               {'heading': 'What to provide',
                 'items': ['`service`: required; provide the non-empty declared Compose service name for the active project, for example `api`. An undeclared name fails instead of producing an observation.']},
               {'heading': 'Result and boundary',
                'items': ['Later steps can use `service`, `declared`, `state`, `healthy`, `containers`, and `published_ports`. On success, `declared` is true: the named service exists in the active Compose configuration. A name that is not declared is a failure, not `declared: false`.',
                          '`state` is the observed service state: `absent` has no materialized container, `starting` has containers still starting, `running` has observed containers running, `stopped` has materialized containers that are not running, and `degraded` includes an unhealthy or mixed runtime state.',
                          '`healthy` is true when the observed health checks are healthy, false when any observed health check is unhealthy, and null when Compose reports no health information.',
                          'This is a point-in-time observation, not a lock or permission to act. Containers can change after the probe, and the operation does not start, stop, or remove anything.']},
               {'heading': 'Do not use for',
                'items': ['Whole-project state; use connector.compose.project when the decision is about the project as '
                          'a whole.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.compose', 'summary': 'Parent Compose connector family'},
                              {'handle': 'connector.compose.project',
                               'summary': 'Sibling probe for project-level state'},
                              {'handle': 'connector.compose.remove',
                               'summary': 'Lifecycle action that targets one stopped service instance'}]},
              {'heading': 'Examples', 'items': ['compose.service with inputs {"service": "api"}']},
              {'heading': 'Inspect next',
               'items': ['connector.compose.remove', 'connector.compose.start', 'connector.compose.stop']}]})

def info():
    return probe(
        name="service",
        human=HUMAN,
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
