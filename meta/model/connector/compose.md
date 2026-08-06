# Compose orchestration connector model

## Public references

- `compose.project`
- `compose.service`
- `compose.start`
- `compose.stop`
- `compose.remove`

## Kind

- `compose.project` — `probe`
- `compose.service` — `probe`
- `compose.start` — `action`
- `compose.stop` — `action`
- `compose.remove` — `action`

## Mental model

- This family models Compose as an orchestration surface, not as a container-interaction shell.
- The primary semantic objects are:
  - project
  - service
  - container instance only as observed runtime evidence of orchestration state
- The family owns state observation and state-changing orchestration intent.
- It does not expose the internal ritual used to achieve a requested running or stopped state.

## Shared bootstrap context

- Preferred raw connector-context fields:
  - `directory: string`
  - `file: string` optional
  - `project_name: string` optional
- Bootstrap may validate and normalize that raw family input into connector-local shared context.
- Later operations should consume connector-local shared context rather than raw playbook or profile data directly.

## `compose.project` output shape

```json
{
  "project": "my-stack",
  "declared_services": ["api", "db", "worker"],
  "state": "running",
  "service_counts": {
    "declared": 3,
    "running": 3,
    "stopped": 0,
    "unhealthy": 0
  },
  "services": {
    "api": {
      "state": "running",
      "healthy": true
    },
    "db": {
      "state": "running",
      "healthy": true
    },
    "worker": {
      "state": "running",
      "healthy": true
    }
  }
}
```

## `compose.service` input shape

- `service: string`

## `compose.service` output shape

```json
{
  "service": "api",
  "declared": true,
  "state": "running",
  "healthy": true,
  "containers": {
    "total": 1,
    "running": 1
  },
  "published_ports": ["8080:8080"]
}
```

## `compose.start` input shape

- optional `service: string`
- omitted `service` means the whole project target

## `compose.start` output shape

Service target example:

```json
{
  "target_kind": "service",
  "target": "api",
  "state": "running",
  "changed": true
}
```

Project target example:

```json
{
  "target_kind": "project",
  "state": "running",
  "changed": true,
  "changed_services": ["api", "worker"]
}
```

## `compose.stop` input shape

- optional `service: string`
- omitted `service` means the whole project target

## `compose.stop` output shape

Service target example:

```json
{
  "target_kind": "service",
  "target": "api",
  "state": "stopped",
  "changed": true
}
```

## `compose.remove` input shape

- `service: string`

## `compose.remove` output shape

```json
{
  "target_kind": "service",
  "target": "api",
  "state": "absent",
  "changed": true
}
```

Project target example:

```json
{
  "target_kind": "project",
  "state": "stopped",
  "changed": true,
  "changed_services": ["api", "worker"]
}
```

## Modeled state vocabulary

### Project probe states

- `down` — the project is not materially present as a running orchestration instance.
- `stopped` — the project exists as known orchestration material but is not running.
- `starting` — startup is in progress.
- `running` — the project is operationally running.
- `degraded` — the project is only partially operational.
- `unknown` — the connector could not honestly determine a narrower state.

### Service probe states

- `absent` — the service has no materialized runtime instance even though the service concept exists in project semantics.
- `stopped` — the service is materially present but not running.
- `starting` — startup is in progress.
- `running` — the service is operationally running.
- `degraded` — the service is only partially operational, for example unhealthy or incompletely running.
- `unknown` — the connector could not honestly determine a narrower state.

### Action result states

- `compose.start` uses:
  - `running`
  - `degraded`
  - `failed`
- `compose.stop` uses:
  - `stopped`
  - `degraded`
  - `failed`
- `compose.remove` uses:
  - `absent`
  - `degraded`
  - `failed`

## Operational interpretation rules

- `compose.service=absent` means the service is declared but no materialized runtime instance exists.
- `compose.service=stopped` means runtime instance material exists but no instance is running.
- `compose.service=starting` means startup is in progress and state is not yet stable.
- `compose.service=running` means running evidence exists and no degradation evidence is present.
- `compose.service=degraded` means the service is only partially operational, including running-but-unhealthy or incompletely running cases.
- `compose.service=unknown` is the residual honest state when the connector cannot determine a narrower service state.
- `compose.project=down` means declared services have no materialized runtime presence.
- `compose.project=stopped` means project runtime material exists but no service is running.
- `compose.project=starting` means project startup is in progress and final state is not yet stable.
- `compose.project=running` means all relevant services are running and not degraded.
- `compose.project=degraded` means service states are mixed, unhealthy, or only partially operational.
- `compose.project=unknown` is the residual honest state when the connector cannot determine a narrower project state.

## Aggregation and health rules

- Project state is derived from service-level orchestration evidence.
- If all declared services are `absent`, project state is `down`.
- If no declared service is running but materialized stopped service state exists, project state is `stopped`.
- If all relevant services are `running` and none is degraded, project state is `running`.
- Mixed service states or any unhealthy service produce project state `degraded` unless `starting` is the more honest transitional state.
- `healthy=true` is positive health evidence.
- `healthy=false` on a running service produces service state `degraded`.
- `healthy=null` means health is not applicable or not provided and does not by itself imply degradation.

## Modeled semantics

- `compose.project` answers one project-level orchestration question: what state currently applies to this Compose project.
- `compose.service` answers one service-level orchestration question: what state currently applies to this declared service.
- `compose.start` is a desired-state action: make the requested target operationally running under Compose orchestration.
- `compose.stop` is a desired-state action: make the requested target stopped.
- `compose.remove` is a desired-state action: remove one stopped declared service so that no materialized runtime instance remains.
- `compose.start` may internally require pull, build, create, recreate, or start behavior.
- Those internal mechanics are implementation detail rather than public action identity.
- The public contract cares about target, achieved state, changedness, and normalized diagnostics.
- If the target is already operationally running, `compose.start` succeeds with `changed=false` and result state `running`.
- If the target becomes only partially operational after the attempt, `compose.start` returns result state `degraded`.
- If the target does not reach operationally running state, `compose.start` returns result state `failed`.
- If the target is already stopped or down, `compose.stop` succeeds with `changed=false` and result state `stopped`.
- If the target stops only partially, `compose.stop` returns result state `degraded`.
- If the target cannot be meaningfully stopped, `compose.stop` returns result state `failed`.
- `compose.remove` is service-only in the minimal surface and does not implicitly stop a running service.
- If the service is already absent, `compose.remove` succeeds with `changed=false` and result state `absent`.
- If the service is still running or otherwise operational, `compose.remove` fails with `service_running` rather than silently stopping it.
- If the service is removed only partially, `compose.remove` returns result state `degraded`.
- If the service cannot be meaningfully removed, `compose.remove` returns result state `failed`.

## Idempotency and changedness

- `compose.start`, `compose.stop`, and `compose.remove` are idempotent with respect to an already-satisfied target state.
- `changed=true` means the connector materially changed orchestration state or runtime artifacts while pursuing the requested intent.
- `changed=false` means the target was already in the requested state or the attempt produced no material change.
- `changed=false` does not imply failure.

## Failure model

- `service_not_declared` means a service-targeted operation named a service not declared for the active project.
- `project_invalid` means the active Compose project definition could not be treated as a valid orchestration target.
- `orchestrator_unavailable` means the connector could not reach the required Compose orchestration capability.
- `observation_failed` is the residual normalized probe failure.
- `image_unavailable`, `build_failed`, `dependency_failed`, `runtime_start_failed`, `healthcheck_failed`, and `start_failed` are distinct `compose.start` action-level non-success classes.
- `dependency_stop_blocked`, `runtime_stop_failed`, and `stop_failed` are distinct `compose.stop` action-level non-success classes.
- `service_running`, `runtime_remove_failed`, and `remove_failed` are distinct `compose.remove` action-level non-success classes.
- Action result state and failure mode remain distinct: result state reports achieved intent class, while failure mode reports normalized reason for non-success or partial success.

## Boundary model

- The family owns orchestration-state observation and orchestration-control actions only.
- It does not own:
  - command execution inside containers;
  - filesystem interaction inside containers;
  - arbitrary Docker or Compose command passthrough;
  - app-level initialization scripts, migrations, or tests;
  - a generic diagnostic shell surface.
- Container-instance facts may appear in outputs only when they help explain orchestration state.
- Raw CLI output, when preserved, is supplementary detail rather than the primary public contract.
