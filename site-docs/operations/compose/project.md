# Inspect Compose project

You need project-level runtime state before deciding whether to start, stop, or inspect one service.

Probe one Compose project as a single orchestration unit.

## Use when

- A lifecycle decision concerns the project as a whole rather than one declared service.

## What to provide

- `Compose target`: context-defaulted; this operation accepts no operation-local target, so it uses the Compose directory, file, and project name selected by the workflow's playbook or profile settings. To inspect a different project, select settings with different Compose values; this operation has no per-call override.

## Result and boundary

- Later steps can use `project`, `declared_services` (the declared services), `state`, `service_counts`, and `services` from the per-service snapshot.
- This is an observation, not a lock: another process can change Compose state after it is read. It fails when the project cannot be inspected or the orchestration tool is unavailable.

## Do not use for

- Service-specific health or container details; use connector.compose.service for that narrower observation.

## Related references

Use these related references when you need a neighboring operation or more context.


- `ordo-help describe connector.compose`: Parent Compose connector family
- `ordo-help describe connector.compose.service`: Sibling probe for one declared service
- `ordo-help describe connector.compose.start`: Lifecycle action that commonly follows a project-level observation

## Examples

- compose.project with inputs {}

## Inspect next

- connector.compose.service
- connector.compose.start
- operations

## Exact machine contract

Use `ordo-help operation compose.project --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### compose_lifecycle_decisions

Inspect the configured Compose project, make the start decision explicit, then save and check the action result before moving to service cleanup.

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
