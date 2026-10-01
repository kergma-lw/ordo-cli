# Compose service

Decide whether one named Compose service is ready for the next lifecycle action.

Probe one declared Compose service as a single orchestration unit.

## Use when

- A later decision needs the current status of one named service, such as whether it is absent, starting, running, stopped, or degraded.
- You need to distinguish a declared service that has no current container from a service with observed running or unhealthy containers.

## What to provide

- `service`: required; provide the non-empty declared Compose service name for the active project, for example `api`. An undeclared name fails instead of producing an observation.

## Result and boundary

- Later steps can use `service`, `declared`, `state`, `healthy`, `containers`, and `published_ports`. On success, `declared` is true: the named service exists in the active Compose configuration. A name that is not declared is a failure, not `declared: false`.
- `state` is the observed service state: `absent` has no materialized container, `starting` has containers still starting, `running` has observed containers running, `stopped` has materialized containers that are not running, and `degraded` includes an unhealthy or mixed runtime state.
- `healthy` is true when the observed health checks are healthy, false when any observed health check is unhealthy, and null when Compose reports no health information.
- This is a point-in-time observation, not a lock or permission to act. Containers can change after the probe, and the operation does not start, stop, or remove anything.

## Do not use for

- Whole-project state; use connector.compose.project when the decision is about the project as a whole.

## Related references

Use these related references when you need a neighboring operation or more context.


- `ordo-help describe connector.compose`: Parent Compose connector family
- `ordo-help describe connector.compose.project`: Sibling probe for project-level state
- `ordo-help describe connector.compose.remove`: Lifecycle action that targets one stopped service instance

## Examples

- compose.service with inputs {"service": "api"}

## Inspect next

- connector.compose.remove
- connector.compose.start
- connector.compose.stop

## Exact machine contract

Use `ordo-help operation compose.service --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### compose_lifecycle_decisions

Inspect the named service before cleanup, save its observed state, and require an explicit cleanup decision before changing it.

```yaml
version: 0
workflow: compose-lifecycle-decisions
inputs:
  service: {}
  start_project: {}
  remove_service: {}
blocks:
- steps:
  - name: inspect-project
    uses: compose.project
    register: project
  - name: require-project-start-decision
    gate: inputs.start_project and step.project.outputs.state != "running"
  - name: start-project
    uses: compose.start
    register: started
  - name: require-project-running
    gate: step.started.outputs.state == "running"
  - name: inspect-service
    uses: compose.service
    with:
      service: inputs.service
    register: service_before_cleanup
  - name: require-service-cleanup-decision
    gate: inputs.remove_service
  - name: stop-service
    uses: compose.stop
    with:
      service: inputs.service
    register: stopped
  - name: require-service-stopped
    gate: step.stopped.outputs.state == "stopped"
  - name: remove-service
    uses: compose.remove
    with:
      service: inputs.service
    register: removed
  - name: require-service-absent
    gate: step.removed.outputs.state == "absent"
  - name: publish-lifecycle-results
    publish:
      project_state_before_start: step.project.outputs.state
      started_project: step.started.outputs.changed
      service_state_before_cleanup: step.service_before_cleanup.outputs.state
      stopped_service: step.stopped.outputs.changed
      removed_service: step.removed.outputs.changed
```
