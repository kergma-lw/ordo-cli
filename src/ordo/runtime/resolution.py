"""Stable connector resolution without silent shadowing."""

from __future__ import annotations

from dataclasses import dataclass

from ordo.model.connector import Connector, ConnectorRegistry, OperationContract
from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONObject, JSONValue
from ordo.model.profile import Override
from ordo.model.runtime import RuntimeStatus
from ordo.model.workflow import GuardBlock, RunBlock, StepBlock, Workflow

from .guard_expressions import BinaryNode, CallNode, GuardExpressionNode, ListNode, LiteralNode, ParsedGuardExpression, ReferenceNode, UnaryNode, parse_guard_expression
from .providers import ConnectorProvider, get_default_connector_provider


@dataclass(frozen=True, slots=True)
class ResolvedOperation:
    """Resolved public or explicit local operation reference."""

    reference: str
    connector_namespace: str
    operation: OperationContract
    source: str
    declared_with: JSONObject | None = None


@dataclass(frozen=True, slots=True)
class ResolvedExpressionProbe:
    """Resolved probe reference used inside a guard expression."""

    reference: str
    connector_namespace: str
    operation: OperationContract
    source: str
    expression_text: str
    fields: tuple[str, ...] = ()
    arguments: tuple[tuple[str, GuardExpressionNode], ...] = ()


@dataclass(frozen=True, slots=True)
class ResolvedGuardExpression:
    """Resolved string-form guard expression."""

    expr: str
    parsed: ParsedGuardExpression
    probes: tuple[ResolvedExpressionProbe, ...] = ()

    @property
    def reference(self) -> str:
        return self.expr


ResolvedGuard = ResolvedOperation | ResolvedGuardExpression


@dataclass(frozen=True, slots=True)
class ResolvedBuiltinStep:
    """Resolved built-in runtime step."""

    name: str
    builtin: str

    @property
    def reference(self) -> str:
        return self.builtin


ResolvedStep = ResolvedOperation | ResolvedBuiltinStep


@dataclass(frozen=True, slots=True)
class ResolvedGuardBlock:
    """Resolved workflow block containing only guards."""

    block_index: int
    guards: tuple[ResolvedGuard, ...] = ()


@dataclass(frozen=True, slots=True)
class ResolvedStepBlock:
    """Resolved workflow block containing only steps."""

    block_index: int
    steps: tuple[ResolvedStep, ...] = ()


@dataclass(frozen=True, slots=True)
class ResolvedRunBlock:
    """Resolved workflow block containing one reusable fragment run."""

    block_index: int
    run: str


ResolvedWorkflowBlock = ResolvedGuardBlock | ResolvedStepBlock | ResolvedRunBlock


@dataclass(frozen=True, slots=True)
class WorkflowResolution:
    """Structured workflow resolution result."""

    status: RuntimeStatus
    diagnostics: tuple[Diagnostic, ...] = ()
    blocks: tuple[ResolvedWorkflowBlock, ...] = ()
    active_overrides: tuple[Override, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status is RuntimeStatus.OK

    @property
    def resolved_guards(self) -> tuple[ResolvedGuard, ...]:
        return tuple(guard for block in self.blocks if isinstance(block, ResolvedGuardBlock) for guard in block.guards)

    @property
    def resolved_steps(self) -> tuple[ResolvedStep, ...]:
        return tuple(step for block in self.blocks if isinstance(block, ResolvedStepBlock) for step in block.steps)


def resolve_workflow_references(
    workflow: Workflow,
    *,
    registry: ConnectorRegistry | None = None,
    connector_provider: ConnectorProvider | None = None,
    local_connectors: tuple[Connector, ...] = (),
    active_overrides: tuple[Override, ...] = (),
) -> WorkflowResolution:
    """Resolve workflow references against public connectors and explicit local namespaces."""

    public_registry = registry or (connector_provider.registry if connector_provider is not None else get_default_connector_provider().registry)
    diagnostics = _validate_local_connectors(local_connectors=local_connectors, public_registry=public_registry)
    local_registry = ConnectorRegistry(connectors=local_connectors)

    if diagnostics:
        return WorkflowResolution(
            status=RuntimeStatus.RESOLUTION_ERROR,
            diagnostics=tuple(diagnostics),
            active_overrides=active_overrides,
        )

    resolved_blocks: list[ResolvedWorkflowBlock] = []

    for block_index, block in enumerate(workflow.blocks):
        if isinstance(block, GuardBlock):
            resolved_guards: list[ResolvedGuard] = []
            for guard_index, guard in enumerate(block.guards):
                if guard.operation is None:
                    resolved = _resolve_guard_expression(
                        guard.expr or "",
                        path=("blocks", str(block_index), "guards", str(guard_index)),
                        public_registry=public_registry,
                        local_registry=local_registry,
                    )
                    if isinstance(resolved, Diagnostic):
                        diagnostics.append(resolved)
                    else:
                        resolved_guards.append(resolved)
                    continue
                resolved = _resolve_reference(
                    guard.operation.uses,
                    path=("blocks", str(block_index), "guards", str(guard_index), "uses"),
                    public_registry=public_registry,
                    local_registry=local_registry,
                    declared_with=guard.operation.with_,
                )
                if isinstance(resolved, Diagnostic):
                    diagnostics.append(resolved)
                else:
                    resolved_guards.append(resolved)
            resolved_blocks.append(ResolvedGuardBlock(block_index=block_index, guards=tuple(resolved_guards)))
            continue
        if isinstance(block, RunBlock):
            resolved_blocks.append(ResolvedRunBlock(block_index=block_index, run=block.run))
            continue

        resolved_steps: list[ResolvedStep] = []
        for step_index, step in enumerate(block.steps):
            if step.value is not None:
                resolved_steps.append(ResolvedBuiltinStep(name=step.name, builtin="value"))
                continue
            if step.state_set is not None:
                resolved_steps.append(ResolvedBuiltinStep(name=step.name, builtin="state_set"))
                continue
            if step.state_delete is not None:
                resolved_steps.append(ResolvedBuiltinStep(name=step.name, builtin="state_delete"))
                continue
            resolved = _resolve_reference(
                step.operation.uses,
                path=("blocks", str(block_index), "steps", str(step_index), "uses"),
                public_registry=public_registry,
                local_registry=local_registry,
                declared_with=step.operation.with_,
            )
            if isinstance(resolved, Diagnostic):
                diagnostics.append(resolved)
            else:
                resolved_steps.append(resolved)
        resolved_blocks.append(ResolvedStepBlock(block_index=block_index, steps=tuple(resolved_steps)))

    if diagnostics:
        return WorkflowResolution(
            status=RuntimeStatus.RESOLUTION_ERROR,
            diagnostics=tuple(diagnostics),
            blocks=tuple(resolved_blocks),
            active_overrides=active_overrides,
        )

    return WorkflowResolution(
        status=RuntimeStatus.OK,
        diagnostics=(),
        blocks=tuple(resolved_blocks),
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


def _resolve_guard_expression(
    expression: str,
    *,
    path: tuple[str, ...],
    public_registry: ConnectorRegistry,
    local_registry: ConnectorRegistry,
) -> ResolvedGuardExpression | Diagnostic:
    parsed = parse_guard_expression(expression)
    diagnostics: list[Diagnostic] = []
    probes: list[ResolvedExpressionProbe] = []

    def visit(node: GuardExpressionNode) -> None:
        if isinstance(node, ReferenceNode):
            if node.parts[0] == "inputs":
                return
            resolved_reference, fields = split_probe_reference(node.parts, public_registry=public_registry, local_registry=local_registry)
            resolved = _resolve_reference(
                resolved_reference,
                path=path,
                public_registry=public_registry,
                local_registry=local_registry,
            )
            if isinstance(resolved, Diagnostic):
                diagnostics.append(resolved)
                return
            if resolved.operation.kind != "probe":
                diagnostics.append(
                    _diagnostic(
                        code="resolution.guard_expr.action_forbidden",
                        message=f"Guard expressions may reference only probe operations, not '{resolved.reference}'",
                        path=path,
                        reference=resolved.reference,
                    )
                )
                return
            field_diagnostic = _validate_field_path(resolved.operation.outputs, fields, path=path, reference=resolved.reference)
            if field_diagnostic is not None:
                diagnostics.append(field_diagnostic)
                return
            probes.append(
                ResolvedExpressionProbe(
                    reference=resolved.reference,
                    connector_namespace=resolved.connector_namespace,
                    operation=resolved.operation,
                    source=resolved.source,
                    expression_text=expression[node.start : node.end],
                    fields=fields,
                )
            )
            return
        if isinstance(node, CallNode):
            resolved = _resolve_reference(
                ".".join(node.target.parts),
                path=path,
                public_registry=public_registry,
                local_registry=local_registry,
            )
            if isinstance(resolved, Diagnostic):
                diagnostics.append(resolved)
                return
            if resolved.operation.kind != "probe":
                diagnostics.append(
                    _diagnostic(
                        code="resolution.guard_expr.action_forbidden",
                        message=f"Guard expressions may reference only probe operations, not '{resolved.reference}'",
                        path=path,
                        reference=resolved.reference,
                    )
                )
                return
            field_diagnostic = _validate_field_path(resolved.operation.outputs, node.fields, path=path, reference=resolved.reference)
            if field_diagnostic is not None:
                diagnostics.append(field_diagnostic)
                return
            probes.append(
                ResolvedExpressionProbe(
                    reference=resolved.reference,
                    connector_namespace=resolved.connector_namespace,
                    operation=resolved.operation,
                    source=resolved.source,
                    expression_text=expression[node.start : node.end],
                    fields=node.fields,
                    arguments=tuple((argument.name, argument.value) for argument in node.arguments),
                )
            )
            for argument in node.arguments:
                visit(argument.value)
            return
        if isinstance(node, ListNode):
            for item in node.items:
                visit(item)
            return
        if isinstance(node, UnaryNode):
            visit(node.operand)
            return
        if isinstance(node, BinaryNode):
            visit(node.left)
            visit(node.right)
            return
        if isinstance(node, LiteralNode):
            return

    visit(parsed.root)
    if diagnostics:
        return diagnostics[0]
    return ResolvedGuardExpression(expr=expression, parsed=parsed, probes=tuple(probes))


def split_probe_reference(
    parts: tuple[str, ...],
    *,
    public_registry: ConnectorRegistry | None,
    local_registry: ConnectorRegistry | None,
) -> tuple[str, tuple[str, ...]]:
    for end in range(len(parts), 1, -1):
        candidate = ".".join(parts[:end])
        if public_registry is None and local_registry is None:
            return candidate, parts[end:]
        if (public_registry is not None and public_registry.get_operation(candidate) is not None) or (
            local_registry is not None and local_registry.get_operation(candidate) is not None
        ):
            fields = parts[end:]
            return candidate, fields
    return ".".join(parts), ()


def _resolve_reference(
    reference: str,
    *,
    path: tuple[str, ...],
    public_registry: ConnectorRegistry,
    local_registry: ConnectorRegistry,
    declared_with: JSONObject | None = None,
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
            declared_with={} if declared_with is None else dict(declared_with),
        )

    if local_operation is not None:
        namespace, _, _ = reference.partition(".")
        return ResolvedOperation(
            reference=reference,
            connector_namespace=namespace,
            operation=local_operation,
            source="local",
            declared_with={} if declared_with is None else dict(declared_with),
        )

    return _diagnostic(
        code="resolution.unknown_operation",
        message=f"Unknown connector operation reference '{reference}'",
        path=path,
        reference=reference,
    )


def _validate_field_path(
    outputs: dict[str, JSONValue],
    fields: tuple[str, ...],
    *,
    path: tuple[str, ...],
    reference: str,
) -> Diagnostic | None:
    current: JSONValue = outputs
    walked: list[str] = []
    for field in fields:
        if not isinstance(current, dict) or field not in current:
            dotted_path = ".".join(walked + [field])
            return _diagnostic(
                code="resolution.guard_expr.field_unknown",
                message=f"Guard expression field path '{dotted_path}' is not documented for '{reference}'",
                path=path,
                reference=reference,
                field_path=dotted_path,
            )
        current = current[field]
        walked.append(field)
    return None


def _diagnostic(code: str, message: str, path: tuple[str, ...], **details: object) -> Diagnostic:
    return Diagnostic(code=code, level="error", message=message, path=path, details=details)
