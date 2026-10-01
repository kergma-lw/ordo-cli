# Compose stop

You need a running Compose target quiesced before cleanup, mutation, or another orchestration phase.

Stop one Compose project or one declared Compose service.

## Use when

- Omit service to stop the whole project, or provide one declared service name to stop only that service.

## What to provide

- `service`: optional; omit it to stop the project, or provide one declared service name to stop only that service.

## Result and boundary

- Later steps can use `target_kind`, `state`, and `changed`. A successful stop reports `state=stopped`; an already stopped or down target reports `changed=false`, while a partial stop reports `state=degraded`. Service-targeted results also include `target`. A failure does not prove that the target stopped.

## Do not use for

- Removing stopped runtime instances; use connector.compose.remove when the intent is cleanup rather than stop.
- Pure observation; use connector.compose.project or connector.compose.service when you only need state.
- Assuming stop removes a service instance. A successful stop reports state stopped; an already stopped or down target reports changed false, while a partial stop reports degraded.

## Related references

Use these related references when you need a neighboring operation or more context.


- `ordo-help describe connector.compose`: Parent Compose connector family
- `ordo-help describe connector.compose.start`: Sibling lifecycle action for bringing a target up
- `ordo-help describe connector.compose.remove`: Cleanup action that often follows a successful stop

## Examples

- compose.stop with inputs {}
- compose.stop with inputs {"service": "api"}

## Inspect next

- connector.compose.remove
- connector.compose.start
- connector.compose.service

## Exact machine contract

Use `ordo-help operation compose.stop --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### compose_lifecycle_decisions

Stop one named service only after an explicit cleanup decision, save the result, and require `stopped` before removal.

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
