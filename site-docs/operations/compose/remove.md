# Compose remove

You need cleanup of one stopped service instance after it is no longer needed.

Remove one stopped materialized Compose service instance.

## Use when

- Provide one non-empty declared service name. This action has no project-wide form.

## What to provide

- `service`: required; provide one non-empty declared service name. This action has no project-wide form.

## Result and boundary

- Later steps can use `target_kind`, `target`, `state`, and `changed`. Success reports `state=absent`, including an already absent service with `changed=false`; a running, starting, or degraded service is rejected without an implicit stop.

## Do not use for

- Stopping a still-running target; use connector.compose.stop first when runtime is still active.
- Whole-project lifecycle changes; use connector.compose.start or connector.compose.stop when the intent is project/service runtime state rather than removal.
- Assuming removal stops a service. A running, starting, or degraded service is rejected without an implicit stop; success reports state absent, including an already absent service with changed false.

## Related references

Use these related references when you need a neighboring operation or more context.


- `ordo-help describe connector.compose`: Parent Compose connector family
- `ordo-help describe connector.compose.service`: Service-level observation that can confirm stopped state before removal
- `ordo-help describe connector.compose.stop`: Sibling lifecycle action often needed before removal

## Examples

- compose.remove with inputs {"service": "api"}

## Inspect next

- connector.compose.stop
- connector.compose.service
- operations

## Exact machine contract

Use `ordo-help operation compose.remove --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### compose_lifecycle_decisions

Remove the named service only after the saved stop result is `stopped`, then save and require the final `absent` result before publishing cleanup facts.

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
