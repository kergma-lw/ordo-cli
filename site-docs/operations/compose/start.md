# Start Compose project or service

You need the requested Compose target running before later workflow steps continue.

Request that one Compose project or declared service run, then report the state observed after the request.

## Use when

- A project-wide startup or one declared service must be asked to run before another step.

## What to provide

- `service`: optional; omit it to start the project, or provide one declared service name to target only that service.

## Result and boundary

- After Compose accepts the request, the action observes the target once. A `running` result means that observation found the requested target running; `degraded` means it found only partial operation. Neither result proves application-level readiness for a later step.
- If the Compose command exits nonzero, the action makes one delayed recovery observation. It can still succeed when that observation finds `running`, `starting`, or `degraded`; it does not keep waiting or repeatedly recheck after reporting the result.
- For readiness beyond this action, inspect connector.compose.project or connector.compose.service again and continue only when the returned state and health facts meet the downstream step's needs.
- Later steps can use `target_kind`, `state`, and `changed`: whether the request targeted a project or service, the reported result state, and whether this call changed orchestration state. Service-targeted results also include `target`.

## Do not use for

- Pure observation; use connector.compose.project or connector.compose.service when you only need state.
- Removing stopped runtime instances; use connector.compose.remove for that cleanup action.

## Related references

Use these related references when you need a neighboring operation or more context.


- `ordo-help describe connector.compose`: Parent Compose connector family
- `ordo-help describe connector.compose.project`: Project-level observation that can precede a start decision
- `ordo-help describe connector.compose.service`: Service-level readiness and health observation after a start
- `ordo-help describe connector.compose.stop`: Sibling lifecycle action for bringing a running target down

## Examples

- compose.start with inputs {}
- compose.start with inputs {"service": "api"}

## Inspect next

- connector.compose.project
- connector.compose.service
- connector.compose.stop

## Exact machine contract

Use `ordo-help operation compose.start --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### compose_lifecycle_decisions

Start the configured project only after an explicit decision, register the result, and require `running` before later service work.

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
