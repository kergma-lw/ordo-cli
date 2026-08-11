"""Shared Compose connector helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass

from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, fail_external_command, fail_with_diagnostic


@dataclass(frozen=True, slots=True)
class ServiceObservation:
    service: str
    declared: bool
    state: str
    healthy: bool | None
    containers_total: int
    containers_running: int
    published_ports: tuple[str, ...]
    materialized: bool

    def to_outputs(self) -> dict[str, object]:
        return {
            "service": self.service,
            "declared": self.declared,
            "state": self.state,
            "healthy": self.healthy,
            "containers": {
                "total": self.containers_total,
                "running": self.containers_running,
            },
            "published_ports": list(self.published_ports),
        }


@dataclass(frozen=True, slots=True)
class ProjectObservation:
    project: str
    declared_services: tuple[str, ...]
    state: str
    service_counts: dict[str, int]
    services: dict[str, dict[str, object]]

    def to_outputs(self) -> dict[str, object]:
        return {
            "project": self.project,
            "declared_services": list(self.declared_services),
            "state": self.state,
            "service_counts": dict(self.service_counts),
            "services": {name: dict(summary) for name, summary in self.services.items()},
        }


def observe_project(ctx: OperationContext) -> ProjectObservation | OperationOutcome:
    inventory = _load_project_inventory(ctx)
    if isinstance(inventory, OperationOutcome):
        return inventory
    declared_services, runtime_entries = inventory
    service_observations = [
        _observe_declared_service(service_name, runtime_entries)
        for service_name in declared_services
    ]
    state = _project_state(service_observations)
    unhealthy_count = sum(1 for item in service_observations if item.healthy is False)
    running_count = sum(1 for item in service_observations if item.state == "running")
    stopped_count = sum(1 for item in service_observations if item.state == "stopped")
    project_name = _project_name(ctx, runtime_entries)
    return ProjectObservation(
        project=project_name,
        declared_services=tuple(declared_services),
        state=state,
        service_counts={
            "declared": len(service_observations),
            "running": running_count,
            "stopped": stopped_count,
            "unhealthy": unhealthy_count,
        },
        services={
            item.service: {"state": item.state, "healthy": item.healthy}
            for item in service_observations
        },
    )


def observe_service(ctx: OperationContext, service: str) -> ServiceObservation | OperationOutcome:
    inventory = _load_project_inventory(ctx)
    if isinstance(inventory, OperationOutcome):
        return inventory
    declared_services, runtime_entries = inventory
    if service not in declared_services:
        return fail_with_diagnostic(
            code="service_not_declared",
            summary=f"Compose service '{service}' is not declared for the active project",
            diagnostic_code="probe.compose_service.not_declared",
            reference=ctx.reference,
            details={"service": service, "declared_services": list(declared_services)},
        )
    return _observe_declared_service(service, runtime_entries)


def compose_command(ctx: OperationContext, *args: str) -> list[str]:
    bootstrap_context = ctx.bootstrap().context
    command = ["docker", "compose"]
    compose_file = bootstrap_context.get("compose_file")
    if isinstance(compose_file, str) and compose_file.strip():
        command.extend(["-f", compose_file])
    project_name = bootstrap_context.get("project_name")
    if isinstance(project_name, str) and project_name.strip():
        command.extend(["--project-name", project_name])
    command.extend(args)
    return command


def map_start_failure(ctx: OperationContext, exc: MappedOutcomeError, *, service: str | None) -> OperationOutcome:
    text = _combined_text(exc.outcome.raw).lower()
    if _contains_any(text, "pull access denied", "not found", "manifest unknown", "image not found", "no such image"):
        code = "image_unavailable"
        diagnostic_code = "action.compose_start.image_unavailable"
        summary = _start_failure_summary(service, "required image is unavailable")
    elif _contains_any(text, "build", "failed to solve", "executor failed running"):
        code = "build_failed"
        diagnostic_code = "action.compose_start.build_failed"
        summary = _start_failure_summary(service, "image build failed")
    elif _contains_any(text, "dependency failed", "depends_on", "dependency"):
        code = "dependency_failed"
        diagnostic_code = "action.compose_start.dependency_failed"
        summary = _start_failure_summary(service, "a dependency failed to start")
    elif _contains_any(text, "health", "unhealthy"):
        code = "healthcheck_failed"
        diagnostic_code = "action.compose_start.healthcheck_failed"
        summary = _start_failure_summary(service, "health checks failed")
    elif _contains_any(text, "failed", "error", "cannot", "unable"):
        code = "runtime_start_failed"
        diagnostic_code = "action.compose_start.runtime_start_failed"
        summary = _start_failure_summary(service, "runtime startup failed")
    else:
        code = "start_failed"
        diagnostic_code = "action.compose_start.start_failed"
        summary = _start_failure_summary(service, "the target could not be started")
    return fail_external_command(
        code=code,
        summary=summary,
        diagnostic_code=diagnostic_code,
        reference=ctx.reference,
        details={"service": service} if service is not None else {},
        raw=exc.outcome.raw,
        tool="docker",
        system="compose",
    )


def map_stop_failure(ctx: OperationContext, exc: MappedOutcomeError, *, service: str | None) -> OperationOutcome:
    text = _combined_text(exc.outcome.raw).lower()
    if _contains_any(text, "dependency", "depends_on"):
        code = "dependency_stop_blocked"
        diagnostic_code = "action.compose_stop.dependency_stop_blocked"
        summary = _stop_failure_summary(service, "a dependency prevented clean shutdown")
    elif _contains_any(text, "failed", "error", "cannot", "unable"):
        code = "runtime_stop_failed"
        diagnostic_code = "action.compose_stop.runtime_stop_failed"
        summary = _stop_failure_summary(service, "runtime shutdown failed")
    else:
        code = "stop_failed"
        diagnostic_code = "action.compose_stop.stop_failed"
        summary = _stop_failure_summary(service, "the target could not be stopped")
    return fail_external_command(
        code=code,
        summary=summary,
        diagnostic_code=diagnostic_code,
        reference=ctx.reference,
        details={"service": service} if service is not None else {},
        raw=exc.outcome.raw,
        tool="docker",
        system="compose",
    )


def map_remove_failure(ctx: OperationContext, exc: MappedOutcomeError, *, service: str) -> OperationOutcome:
    text = _combined_text(exc.outcome.raw).lower()
    if _contains_any(text, "running", "in use", "is active"):
        code = "service_running"
        diagnostic_code = "action.compose_remove.service_running"
        summary = f"Compose service '{service}' is still running and cannot be removed"
    elif _contains_any(text, "failed", "error", "cannot", "unable"):
        code = "runtime_remove_failed"
        diagnostic_code = "action.compose_remove.runtime_remove_failed"
        summary = f"Compose service '{service}' could not be removed because runtime removal failed"
    else:
        code = "remove_failed"
        diagnostic_code = "action.compose_remove.remove_failed"
        summary = f"Compose service '{service}' could not be removed"
    return fail_external_command(
        code=code,
        summary=summary,
        diagnostic_code=diagnostic_code,
        reference=ctx.reference,
        details={"service": service},
        raw=exc.outcome.raw,
        tool="docker",
        system="compose",
    )


def _load_project_inventory(ctx: OperationContext) -> tuple[list[str], list[dict[str, object]]] | OperationOutcome:
    declared_services = _load_declared_services(ctx)
    if isinstance(declared_services, OperationOutcome):
        return declared_services
    runtime_entries = _load_runtime_entries(ctx)
    if isinstance(runtime_entries, OperationOutcome):
        return runtime_entries
    return declared_services, runtime_entries


def _load_declared_services(ctx: OperationContext) -> list[str] | OperationOutcome:
    try:
        command = ctx.command(
            compose_command(ctx, "config", "--services"),
            failures={"os_error": "observation_failed", "nonzero": "project_invalid"},
        )
    except MappedOutcomeError as exc:
        return fail_with_diagnostic(
            code=exc.outcome.status,
            summary="Compose project definition could not be resolved",
            diagnostic_code="compose.project.config_failed",
            reference=ctx.reference,
            raw=exc.outcome.raw,
        )
    services = [line.strip() for line in command.stdout.splitlines() if line.strip()]
    return list(dict.fromkeys(services))


def _load_runtime_entries(ctx: OperationContext) -> list[dict[str, object]] | OperationOutcome:
    try:
        command = ctx.command(
            compose_command(ctx, "ps", "--all", "--format", "json"),
            failures={"os_error": "observation_failed", "nonzero": "observation_failed"},
        )
    except MappedOutcomeError as exc:
        return fail_with_diagnostic(
            code="observation_failed",
            summary="Compose runtime state could not be observed",
            diagnostic_code="compose.project.ps_failed",
            reference=ctx.reference,
            raw=exc.outcome.raw,
        )
    return _parse_ps_entries(ctx, command.stdout)


def _parse_ps_entries(ctx: OperationContext, stdout: str) -> list[dict[str, object]] | OperationOutcome:
    payload = stdout.strip()
    if not payload:
        return []
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError:
        try:
            decoded = [json.loads(line) for line in payload.splitlines() if line.strip()]
        except json.JSONDecodeError as exc:
            return fail_with_diagnostic(
                code="observation_failed",
                summary="Compose runtime output was not valid JSON",
                diagnostic_code="compose.project.invalid_ps_json",
                reference=ctx.reference,
                details={"error": str(exc)},
                raw={"stdout": stdout},
            )
    if isinstance(decoded, dict):
        decoded = [decoded]
    if not isinstance(decoded, list) or any(not isinstance(item, dict) for item in decoded):
        return fail_with_diagnostic(
            code="observation_failed",
            summary="Compose runtime output did not match the expected JSON shape",
            diagnostic_code="compose.project.invalid_ps_shape",
            reference=ctx.reference,
            raw={"stdout": stdout},
        )
    return [dict(item) for item in decoded]


def _observe_declared_service(service: str, runtime_entries: list[dict[str, object]]) -> ServiceObservation:
    entries = [entry for entry in runtime_entries if _entry_service_name(entry) == service]
    if not entries:
        return ServiceObservation(
            service=service,
            declared=True,
            state="absent",
            healthy=None,
            containers_total=0,
            containers_running=0,
            published_ports=(),
            materialized=False,
        )

    running_count = 0
    starting_present = False
    degraded_present = False
    publishers: list[str] = []
    health_values: list[bool | None] = []
    for entry in entries:
        entry_state = _entry_observation_state(entry)
        if entry_state == "running":
            running_count += 1
        elif entry_state == "starting":
            starting_present = True
        elif entry_state == "degraded":
            degraded_present = True
        publishers.extend(_entry_publishers(entry))
        health_values.append(_entry_health(entry))

    if running_count == 0 and not starting_present and not degraded_present:
        state = "stopped"
    elif starting_present and running_count == 0 and not degraded_present:
        state = "starting"
    elif degraded_present:
        state = "degraded"
    elif starting_present:
        state = "degraded"
    else:
        state = "running"

    healthy = _aggregate_health(health_values)
    if state == "running" and healthy is False:
        state = "degraded"

    return ServiceObservation(
        service=service,
        declared=True,
        state=state,
        healthy=healthy,
        containers_total=len(entries),
        containers_running=running_count,
        published_ports=tuple(dict.fromkeys(publishers)),
        materialized=True,
    )


def _project_state(service_observations: list[ServiceObservation]) -> str:
    if not service_observations:
        return "unknown"
    states = [item.state for item in service_observations]
    if all(state == "absent" for state in states):
        return "down"
    if all(state in {"absent", "stopped"} for state in states):
        return "stopped"
    if all(state == "running" for state in states):
        return "running"
    if any(state == "degraded" for state in states):
        return "degraded"
    if any(state == "starting" for state in states) and all(state in {"starting", "running"} for state in states):
        return "starting"
    if any(state == "running" for state in states) or any(state == "starting" for state in states):
        return "degraded"
    return "unknown"


def _project_name(ctx: OperationContext, runtime_entries: list[dict[str, object]]) -> str:
    bootstrap_context = ctx.bootstrap().context
    project_name = bootstrap_context.get("project_name")
    if isinstance(project_name, str) and project_name.strip():
        return project_name
    for entry in runtime_entries:
        candidate = entry.get("Project") or entry.get("project")
        if isinstance(candidate, str) and candidate.strip():
            return candidate
    project_directory = bootstrap_context.get("project_directory")
    if isinstance(project_directory, str) and project_directory.strip():
        return project_directory.rstrip("/").rsplit("/", 1)[-1]
    return "compose-project"


def _entry_service_name(entry: dict[str, object]) -> str | None:
    candidate = entry.get("Service") or entry.get("service")
    if isinstance(candidate, str) and candidate.strip():
        return candidate
    return None


def _entry_health(entry: dict[str, object]) -> bool | None:
    health = entry.get("Health") or entry.get("health")
    status = _string_value(health)
    if status is None:
        return None
    normalized = status.strip().lower()
    if normalized == "healthy":
        return True
    if normalized == "unhealthy":
        return False
    return None


def _entry_observation_state(entry: dict[str, object]) -> str:
    health = _entry_health(entry)
    state_text = " ".join(
        filter(
            None,
            [
                _string_value(entry.get("State")),
                _string_value(entry.get("state")),
                _string_value(entry.get("Status")),
                _string_value(entry.get("status")),
            ],
        )
    ).lower()
    if health is False:
        return "degraded"
    if any(token in state_text for token in ("starting", "restarting", "created")):
        return "starting"
    if any(token in state_text for token in ("running", "up ", "up(")) or state_text == "up":
        return "running"
    if any(token in state_text for token in ("exited", "stopped", "dead", "removing")):
        return "stopped"
    if health is True:
        return "running"
    return "stopped"


def _entry_publishers(entry: dict[str, object]) -> list[str]:
    publishers = entry.get("Publishers") or entry.get("publishers")
    if publishers in (None, ""):
        return []
    if isinstance(publishers, list):
        rendered: list[str] = []
        for item in publishers:
            if isinstance(item, str):
                rendered.append(item)
                continue
            if not isinstance(item, dict):
                continue
            published = item.get("PublishedPort") or item.get("published_port") or item.get("published")
            target = item.get("TargetPort") or item.get("target_port") or item.get("target")
            host_ip = item.get("URL") or item.get("HostIp") or item.get("host_ip")
            protocol = item.get("Protocol") or item.get("protocol")
            left = str(published) if published is not None else ""
            right = str(target) if target is not None else ""
            value = f"{left}:{right}" if left and right else left or right
            if isinstance(protocol, str) and protocol.strip():
                value = f"{value}/{protocol}"
            if isinstance(host_ip, str) and host_ip.strip() and value:
                value = f"{host_ip}:{value}"
            if value:
                rendered.append(value)
        return rendered
    if isinstance(publishers, str):
        return [publishers]
    return []


def _aggregate_health(values: list[bool | None]) -> bool | None:
    if any(value is False for value in values):
        return False
    if any(value is True for value in values):
        return True
    return None


def _combined_text(raw: dict[str, object]) -> str:
    stdout = raw.get("stdout")
    stderr = raw.get("stderr")
    return f"{stdout if isinstance(stdout, str) else ''}\n{stderr if isinstance(stderr, str) else ''}"


def _contains_any(text: str, *needles: str) -> bool:
    return any(needle in text for needle in needles)


def _start_failure_summary(service: str | None, reason: str) -> str:
    if service is None:
        return f"Compose project could not be started because {reason}"
    return f"Compose service '{service}' could not be started because {reason}"


def _stop_failure_summary(service: str | None, reason: str) -> str:
    if service is None:
        return f"Compose project could not be stopped because {reason}"
    return f"Compose service '{service}' could not be stopped because {reason}"


def _string_value(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None
