# Compose orchestration connector requirements

## Role

- `compose.project` is the public `compose` connector probe for observing one Compose project as an orchestration unit.
- `compose.service` is the public `compose` connector probe for observing one declared service inside one Compose project.
- `compose.start` is the public `compose` connector action for bringing one Compose target into operational running state.
- `compose.stop` is the public `compose` connector action for stopping one Compose target.
- `compose.remove` is the public `compose` connector action for removing one stopped materialized Compose service instance.

## Surface size rule

- The v0 public `compose` surface should stay minimal and orthogonal.
- The intended v0 surface is exactly:
  - `compose.project`
  - `compose.service`
  - `compose.start`
  - `compose.stop`
  - `compose.remove`
- The connector must not mirror the full Docker Compose CLI surface as public Ordo operations.

## Orchestration boundary

- The `compose` connector owns orchestration state and orchestration control.
- It may observe project, service, and container-instance facts only insofar as those facts express orchestration state.
- It must not own execution inside containers.
- It must not expose public operations for arbitrary command execution, file access, or shell interaction inside containers.
- It must not turn containers into general workflow compute targets.

## Raw connector context

- The family-level raw connector context should use stable family-owned field names.
- The preferred raw context fields are:
  - `directory`
  - optional `file`
  - optional `project_name`
- This context is ambient bootstrap input, not workflow-readable semantics.

## Required questions

- `compose.project` must answer what orchestration state currently applies to the active Compose project.
- `compose.service` must answer what orchestration state currently applies to one requested declared service.
- `compose.start` must answer whether the requested target was brought into operational running state.
- `compose.stop` must answer whether the requested target was stopped.
- `compose.remove` must answer whether the requested service target was removed so that no materialized runtime instance remains.

## Required inputs

- `compose.project` takes no operation-local inputs in the normal ambient-context case.
- `compose.service` requires:
  - `service`
- `compose.start` accepts either:
  - no `service` input, meaning the whole project target;
  - one `service` input, meaning one service target.
- `compose.stop` accepts either:
  - no `service` input, meaning the whole project target;
  - one `service` input, meaning one service target.
- `compose.remove` requires:
  - `service`
- `service`, when accepted, must be a non-empty string naming one declared service.
- The v0 public surface must not accept service lists or arbitrary selectors.

## Project observation contract

- `compose.project` must return at least:
  - `project`
  - `declared_services`
  - `state`
  - `service_counts`
  - `services`
- `state` must use connector-owned project-state vocabulary rather than raw transport wording.
- The required project-state vocabulary is:
  - `down`
  - `stopped`
  - `starting`
  - `running`
  - `degraded`
  - `unknown`
- `service_counts` must expose at least:
  - `declared`
  - `running`
  - `stopped`
  - `unhealthy`
- `services` must expose a compact per-service summary rather than a raw inspect dump.

## Service observation contract

- `compose.service` must return at least:
  - `service`
  - `declared`
  - `state`
  - `healthy`
  - `containers`
  - `published_ports`
- The required service-state vocabulary is:
  - `absent`
  - `stopped`
  - `starting`
  - `running`
  - `degraded`
  - `unknown`
- `healthy` may be `true`, `false`, or `null` when no health information applies.
- `containers` must expose bounded count facts rather than raw container inspection payloads.

## State interpretation rules

- For `compose.service`:
  - use `absent` when the service is declared but no materialized runtime instance exists;
  - use `stopped` when runtime instance material exists but no instance is running;
  - use `starting` when startup is in progress and the runtime state is not yet stable;
  - use `running` when running evidence exists and no degradation evidence is present;
  - use `degraded` when the service is only partially operational, including running-but-unhealthy or incompletely running cases;
  - use `unknown` only when the connector cannot honestly determine a narrower service state.
- For `compose.project`:
  - use `down` when declared services have no materialized runtime presence;
  - use `stopped` when project runtime material exists but no service is running;
  - use `starting` when project startup is in progress and final state is not yet stable;
  - use `running` when all relevant services are running and not degraded;
  - use `degraded` when service states are mixed, unhealthy, or only partially operational;
  - use `unknown` only when the connector cannot honestly determine a narrower project state.

## Aggregation and health rules

- `compose.project` must derive project state from service-level orchestration evidence rather than from one raw CLI phrase.
- If all declared services are `absent`, project state must be `down`.
- If no declared service is running but materialized stopped service state exists, project state must be `stopped`.
- If all relevant services are `running` and none is degraded, project state must be `running`.
- Mixed service states or any unhealthy service must produce project state `degraded` unless `starting` is the more honest transitional state.
- `healthy=false` on a running service must produce service state `degraded`.
- `healthy=null` means health is not applicable or not provided by the orchestration surface; it must not by itself imply degradation.

## Start action contract

- `compose.start` is an intent-level orchestration action.
- It means: bring the requested project or service target into operational running state under Compose orchestration.
- The public contract must not promise one specific internal ritual such as strict CLI `start` semantics only.
- A successful `compose.start` may internally require build, pull, create, recreate, or start behavior, provided the public action meaning stays the same.
- `compose.start` must return at least:
  - `target_kind`
  - `state`
  - `changed`
- When the target is one service, it must also return:
  - `target`
- When helpful, it may also return:
  - `changed_services`
- `target_kind` must be either `project` or `service`.
- `state` in the action result must use:
  - `running`
  - `degraded`
  - `failed`
- If the requested target is already operationally running, `compose.start` must succeed with `changed=false` and result state `running`.
- If the requested target becomes only partially operational after the attempt, `compose.start` must return result state `degraded` rather than `running`.
- If the requested target does not reach operationally running state, `compose.start` must return result state `failed`.

## Stop action contract

- `compose.stop` means: stop the requested project or service target.
- `compose.stop` does not imply full project teardown.
- `compose.stop` must return at least:
  - `target_kind`
  - `state`
  - `changed`
- When the target is one service, it must also return:
  - `target`
- When helpful, it may also return:
  - `changed_services`
- `target_kind` must be either `project` or `service`.
- `state` in the action result must use:
  - `stopped`
  - `degraded`
  - `failed`
- If the requested target is already stopped or down, `compose.stop` must succeed with `changed=false` and result state `stopped`.
- If the requested target stops only partially, `compose.stop` must return result state `degraded`.
- If the requested target cannot be meaningfully stopped, `compose.stop` must return result state `failed`.

## Remove action contract

- `compose.remove` means: remove the materialized runtime instance for one declared service.
- `compose.remove` is service-only in the minimal public surface.
- `compose.remove` must not silently redefine itself as stop-and-remove in v0.
- If the requested service is still running or otherwise operational, `compose.remove` must fail explicitly instead of stopping it implicitly.
- `compose.remove` must return at least:
  - `target_kind`
  - `target`
  - `state`
  - `changed`
- `target_kind` must be `service`.
- `state` in the action result must use:
  - `absent`
  - `degraded`
  - `failed`
- If the requested service is already absent, `compose.remove` must succeed with `changed=false` and result state `absent`.
- If the requested service is removed only partially, `compose.remove` must return result state `degraded`.
- If the requested service cannot be meaningfully removed, `compose.remove` must return result state `failed`.

## Idempotency and changedness rules

- `compose.start`, `compose.stop`, and `compose.remove` must be idempotent with respect to an already-satisfied target state.
- `changed=true` means the connector materially changed orchestration state or runtime artifacts while pursuing the requested intent.
- `changed=false` means the target was already in the requested state or the attempt produced no material change.
- `changed=false` does not by itself imply failure.

## Result-state and failure-mode separation

- Action result state and action failure mode must remain distinct.
- Result state reports whether intent was achieved, partially achieved, or not achieved.
- Failure mode reports the normalized reason for non-success or partial success.
- A degraded or failed action result should still preserve the structured target-oriented outcome surface rather than collapsing into raw command failure alone.

## Diagnostics and failure contract

- `compose.start`, `compose.stop`, and `compose.remove` must report intent-level outcome and normalized reason rather than low-level command ritual as the primary contract.
- Human-readable summaries should explain what target was attempted and why the target could not reach the intended state.
- `compose.project` must fail explicitly as one of:
  - `project_invalid`
  - `orchestrator_unavailable`
  - `observation_failed`
- `compose.service` must fail explicitly as one of:
  - `service_not_declared`
  - `project_invalid`
  - `orchestrator_unavailable`
  - `observation_failed`
- `compose.start` must fail explicitly as one of:
  - `service_not_declared`
  - `project_invalid`
  - `orchestrator_unavailable`
  - `image_unavailable`
  - `build_failed`
  - `dependency_failed`
  - `runtime_start_failed`
  - `healthcheck_failed`
  - `start_failed`
- `compose.stop` must fail explicitly as one of:
  - `service_not_declared`
  - `project_invalid`
  - `orchestrator_unavailable`
  - `dependency_stop_blocked`
  - `runtime_stop_failed`
  - `stop_failed`
- `compose.remove` must fail explicitly as one of:
  - `service_not_declared`
  - `service_running`
  - `project_invalid`
  - `orchestrator_unavailable`
  - `runtime_remove_failed`
  - `remove_failed`

## Boundary exclusions

- The v0 public `compose` surface must not include:
  - `compose.exec`
  - arbitrary CLI passthrough
  - in-container file reads
  - in-container shell execution
  - app-level migrations, tests, or scripts
  - a generic logs-scraping surface
- The connector may use container-instance observations as orchestration evidence, but container internals are not the public semantic center.

## Discovery rule

- The public contract should be discoverable through `ordo-help operation compose.project`, `compose.service`, `compose.start`, `compose.stop`, and `compose.remove`.
- Discovery material should make clear that this family is an orchestration-state and orchestration-control surface rather than a general Docker gateway.
