"""Stable connector resolution without silent shadowing."""

from __future__ import annotations

from dataclasses import dataclass

from ordo.model.connector import Connector, ConnectorRegistry, OperationContract
from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONObject, JSONValue
from ordo.model.profile import Override
from ordo.model.runtime import RuntimeStatus
from ordo.model.workflow import GuardBlock, StepBlock, Workflow

from .local_expression_contexts import LocalExpressionContext
from .local_expressions import LOCAL_EXPRESSION_PARSE_ERRORS, parse_local_expression, resolve_workflow_let_reference_node
from .local_expression_engine.core import AdapterBindingNode, AdapterInvocationNode, BinaryNode, BuiltinCallNode, CallNode, FilterApplicationNode, ListNode, LiteralNode, ObjectEntryNode, ObjectNode, ParsedLocalExpressionTree, PipelineNode, ReferenceNode, StateReferenceNode, UnaryNode, ValueExpressionNode, render_expression_text
from .providers import ConnectorProvider, get_default_connector_provider
from .routines import parse_routine_reference, resolve_routine_entry, routine_operation_contract


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
    arguments: tuple[tuple[str, ValueExpressionNode], ...] = ()


@dataclass(frozen=True, slots=True)
class ResolvedConditionExpression:
    """Resolved condition expression under the shared local-expression model."""

    expr: str
    parsed: ParsedLocalExpressionTree
    probes: tuple[ResolvedExpressionProbe, ...] = ()

    @property
    def reference(self) -> str:
        return self.expr


ResolvedGuardExpression = ResolvedConditionExpression
ResolvedGuard = ResolvedOperation | ResolvedConditionExpression


@dataclass(frozen=True, slots=True)
class ResolvedBuiltinStep:
    """Resolved built-in runtime step."""

    name: str
    builtin: str

    @property
    def reference(self) -> str:
        return self.builtin


@dataclass(frozen=True, slots=True)
class ResolvedRunStep:
    """Resolved reusable fragment invocation step."""

    name: str
    run: str

    @property
    def reference(self) -> str:
        return self.run


ResolvedStep = ResolvedOperation | ResolvedBuiltinStep | ResolvedRunStep


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


ResolvedWorkflowBlock = ResolvedGuardBlock | ResolvedStepBlock


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
                        workflow=workflow,
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
                    workflow=workflow,
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
        resolved_steps: list[ResolvedStep] = []
        for step_index, step in enumerate(block.steps):
            if step.value is not None:
                resolved_steps.append(ResolvedBuiltinStep(name=step.name, builtin="value"))
                continue
            if step.result is not None:
                resolved_steps.append(ResolvedBuiltinStep(name=step.name, builtin="result"))
                continue
            if step.publish is not None:
                resolved_steps.append(ResolvedBuiltinStep(name=step.name, builtin="publish"))
                continue
            if step.run is not None:
                resolved_steps.append(ResolvedRunStep(name=step.name, run=step.run))
                continue
            if step.profile_switch is not None:
                resolved_steps.append(ResolvedBuiltinStep(name=step.name, builtin="profile_switch"))
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
                workflow=workflow,
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
    workflow: Workflow,
    path: tuple[str, ...],
    public_registry: ConnectorRegistry,
    local_registry: ConnectorRegistry,
) -> ResolvedConditionExpression | Diagnostic:
    """Resolve one guard-context local expression against the connector registries."""

    parsed_local = parse_local_expression(expression, context=LocalExpressionContext.GUARD)
    parsed = parsed_local.value
    diagnostics: list[Diagnostic] = []
    probes: list[ResolvedExpressionProbe] = []

    def visit(node: ValueExpressionNode) -> None:
        try:
            expanded = resolve_workflow_let_reference_node(node, workflow, context=LocalExpressionContext.GUARD)
        except LOCAL_EXPRESSION_PARSE_ERRORS as exc:
            binding_name = node.parts[0] if isinstance(node, ReferenceNode) and node.parts else "<unknown>"
            diagnostics.append(
                _diagnostic(
                    code="resolution.let_binding.syntax",
                    message=f"Workflow let binding '{binding_name}' is not a valid guard expression",
                    path=path,
                    binding_name=binding_name,
                    binding_path=["let", binding_name],
                    position=exc.position,
                    end=exc.end if exc.end is not None else exc.position,
                    parse_message=exc.message,
                )
            )
            return
        if expanded is not None:
            visit(expanded)
            return
        if isinstance(node, ReferenceNode):
            if node.parts[0] == "inputs":
                return
            resolved_reference, fields = split_probe_reference(node.parts, public_registry=public_registry, local_registry=local_registry)
            resolved = _resolve_reference(
                resolved_reference,
                path=path,
                workflow=workflow,
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
                    expression_text=render_expression_text(node, source=expression),
                    fields=fields,
                )
            )
            return
        if isinstance(node, StateReferenceNode):
            return
        if isinstance(node, CallNode):
            resolved = _resolve_reference(
                ".".join(node.target.parts),
                path=path,
                workflow=workflow,
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
                    expression_text=render_expression_text(node, source=expression),
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
        if isinstance(node, FilterApplicationNode):
            for argument in node.arguments:
                visit(argument)
            return
        if isinstance(node, PipelineNode):
            visit(node.source)
            for filter_node in node.filters:
                visit(filter_node)
            return
        if isinstance(node, BuiltinCallNode):
            for argument in node.arguments:
                visit(argument)
            return
        if isinstance(node, ObjectEntryNode):
            visit(node.value)
            return
        if isinstance(node, ObjectNode):
            for entry in node.entries:
                visit(entry)
            return
        if isinstance(node, AdapterBindingNode):
            visit(node.value)
            return
        if isinstance(node, AdapterInvocationNode):
            for binding in node.bindings:
                visit(binding)
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
    return ResolvedConditionExpression(expr=expression, parsed=parsed, probes=tuple(probes))


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
    workflow: Workflow,
    public_registry: ConnectorRegistry,
    local_registry: ConnectorRegistry,
    declared_with: JSONObject | None = None,
) -> ResolvedOperation | Diagnostic:
    routine_id = parse_routine_reference(reference)
    if routine_id is not None:
        if not routine_id:
            return _diagnostic(
                code="resolution.routine.missing_id",
                message="Routine invocations must declare a non-empty routine id",
                path=path,
                reference=reference,
            )
        resolved = resolve_routine_entry(workflow=workflow, routine_id=routine_id)
        if isinstance(resolved, Diagnostic):
            return Diagnostic(
                code=resolved.code,
                level=resolved.level,
                message=resolved.message,
                path=path,
                details=dict(resolved.details),
            )
        _registry, entry = resolved
        return ResolvedOperation(
            reference=f"routine.{routine_id}",
            connector_namespace="routine",
            operation=routine_operation_contract(entry),
            source="routine",
            declared_with={} if declared_with is None else dict(declared_with),
        )
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
