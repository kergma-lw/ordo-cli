"""Stable connector resolution without silent shadowing."""

from __future__ import annotations

from dataclasses import dataclass

from ordo.connectors import ConnectorRegistry, get_public_connector_registry
from ordo.model.connector import Connector, OperationContract
from ordo.model.diagnostic import Diagnostic
from ordo.model.profile import Override
from ordo.model.runtime import RuntimeStatus
from ordo.model.workflow import Workflow


@dataclass(frozen=True, slots=True)
class ResolvedOperation:
    """Resolved public or explicit local operation reference."""

    reference: str
    connector_namespace: str
    operation: OperationContract
    source: str


@dataclass(frozen=True, slots=True)
class WorkflowResolution:
    """Structured workflow resolution result."""

    status: RuntimeStatus
    diagnostics: tuple[Diagnostic, ...] = ()
    resolved_guards: tuple[ResolvedOperation, ...] = ()
    resolved_steps: tuple[ResolvedOperation, ...] = ()
    active_overrides: tuple[Override, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status is RuntimeStatus.OK


def resolve_workflow_references(
    workflow: Workflow,
    *,
    registry: ConnectorRegistry | None = None,
    local_connectors: tuple[Connector, ...] = (),
    active_overrides: tuple[Override, ...] = (),
) -> WorkflowResolution:
    """Resolve workflow references against public connectors and explicit local namespaces."""

    public_registry = registry or get_public_connector_registry()
    diagnostics = _validate_local_connectors(local_connectors=local_connectors, public_registry=public_registry)
    local_registry = ConnectorRegistry(connectors=local_connectors)

    if diagnostics:
        return WorkflowResolution(
            status=RuntimeStatus.RESOLUTION_ERROR,
            diagnostics=tuple(diagnostics),
            active_overrides=active_overrides,
        )

    resolved_guards: list[ResolvedOperation] = []
    resolved_steps: list[ResolvedOperation] = []

    for index, guard in enumerate(workflow.guards):
        if guard.operation is None:
            diagnostics.append(
                _diagnostic(
                    code="resolution.guard_expr_not_implemented",
                    message="String-form guard expression resolution is not implemented yet",
                    path=("guards", str(index)),
                    expr=guard.expr,
                )
            )
            continue
        resolved = _resolve_reference(
            guard.operation.uses,
            path=("guards", str(index), "uses"),
            public_registry=public_registry,
            local_registry=local_registry,
        )
        if isinstance(resolved, Diagnostic):
            diagnostics.append(resolved)
        else:
            resolved_guards.append(resolved)

    for index, step in enumerate(workflow.steps):
        resolved = _resolve_reference(
            step.operation.uses,
            path=("steps", str(index), "uses"),
            public_registry=public_registry,
            local_registry=local_registry,
        )
        if isinstance(resolved, Diagnostic):
            diagnostics.append(resolved)
        else:
            resolved_steps.append(resolved)

    if diagnostics:
        return WorkflowResolution(
            status=RuntimeStatus.RESOLUTION_ERROR,
            diagnostics=tuple(diagnostics),
            resolved_guards=tuple(resolved_guards),
            resolved_steps=tuple(resolved_steps),
            active_overrides=active_overrides,
        )

    return WorkflowResolution(
        status=RuntimeStatus.OK,
        diagnostics=(),
        resolved_guards=tuple(resolved_guards),
        resolved_steps=tuple(resolved_steps),
        active_overrides=active_overrides,
    )


def _validate_local_connectors(*, local_connectors: tuple[Connector, ...], public_registry: ConnectorRegistry) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    public_namespaces = {connector.namespace for connector in public_registry.list_connectors()}

    for connector in local_connectors:
        if connector.namespace in public_namespaces:
            diagnostics.append(
                _diagnostic(
                    code="resolution.namespace_shadowing",
                    message=f"Local connector namespace '{connector.namespace}' would silently shadow a public connector",
                    path=("connectors", connector.namespace),
                    namespace=connector.namespace,
                )
            )
    return diagnostics


def _resolve_reference(
    reference: str,
    *,
    path: tuple[str, ...],
    public_registry: ConnectorRegistry,
    local_registry: ConnectorRegistry,
) -> ResolvedOperation | Diagnostic:
    public_operation = public_registry.get_operation(reference)
    local_operation = local_registry.get_operation(reference)

    if public_operation is not None and local_operation is not None:
        return _diagnostic(
            code="resolution.operation_shadowing",
            message=f"Reference '{reference}' is ambiguous because a local operation would shadow a public operation",
            path=path,
            reference=reference,
        )

    if public_operation is not None:
        namespace, _, _ = reference.partition(".")
        return ResolvedOperation(
            reference=reference,
            connector_namespace=namespace,
            operation=public_operation,
            source="public",
        )

    if local_operation is not None:
        namespace, _, _ = reference.partition(".")
        return ResolvedOperation(
            reference=reference,
            connector_namespace=namespace,
            operation=local_operation,
            source="local",
        )

    return _diagnostic(
        code="resolution.unknown_operation",
        message=f"Unknown connector operation reference '{reference}'",
        path=path,
        reference=reference,
    )


def _diagnostic(code: str, message: str, path: tuple[str, ...], **details: object) -> Diagnostic:
    return Diagnostic(code=code, level="error", message=message, path=path, details=details)
