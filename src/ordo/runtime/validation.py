"""Strict validation for workflow and profile declarations."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONObject, JSONValue
from ordo.model.profile_contract import PROFILE_CONTRACT
from ordo.model.runtime import RuntimeStatus
from ordo.model.workflow_contract import WORKFLOW_CONTRACT

from .guard_expressions import GuardExpressionParseError, parse_guard_expression, validate_parsed_guard_expression
from .loading import LoadError, load_yaml_document
from .state_paths import StatePathParseError, parse_state_path
from .value_expressions import (
    BuiltinCallNode,
    FilterApplicationNode,
    LiteralNode,
    PipelineNode,
    ReferenceNode,
    StateReferenceNode,
    StepReferenceNode,
    ValueExpressionNode,
    ValueExpressionParseError,
    collect_step_references,
    parse_value_expression,
)

USES_PATTERN = re.compile(r"^[a-z0-9]+([._-][a-z0-9]+)*$")
REGISTER_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def _field_names(items: list[JSONObject]) -> frozenset[str]:
    return frozenset(item["name"] for item in items if isinstance(item.get("name"), str))


WORKFLOW_ALLOWED_FIELDS = _field_names(WORKFLOW_CONTRACT["top_level_fields"])
BLOCK_ALLOWED_FIELDS = frozenset({"guards", "steps"})
CALL_ALLOWED_FIELDS = frozenset({"uses", "with"})
STEP_ALLOWED_FIELDS = frozenset().union(
    *(
        frozenset(form["required_fields"]) | frozenset(form["optional_fields"])
        for form in WORKFLOW_CONTRACT["step_forms"]
        if isinstance(form, dict)
    )
)
PROFILE_ALLOWED_FIELDS = _field_names(PROFILE_CONTRACT["top_level_fields"])
OVERRIDE_ALLOWED_FIELDS = _field_names(PROFILE_CONTRACT["override_fields"])


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Machine-usable validation result."""

    document_kind: str
    status: RuntimeStatus
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status is RuntimeStatus.OK


def validate_workflow_text(text: str, *, source: str = "<memory>") -> ValidationReport:
    """Validate workflow YAML text against the stable v0 contract."""

    try:
        payload = load_yaml_document(text, source=source)
    except LoadError as exc:
        return ValidationReport(document_kind="workflow", status=RuntimeStatus.VALIDATION_ERROR, diagnostics=exc.diagnostics)

    return validate_workflow_document(payload, source=source)


def validate_profile_text(text: str, *, source: str = "<memory>") -> ValidationReport:
    """Validate profile YAML text against the current v0 profile contract."""

    try:
        payload = load_yaml_document(text, source=source)
    except LoadError as exc:
        return ValidationReport(document_kind="profile", status=RuntimeStatus.VALIDATION_ERROR, diagnostics=exc.diagnostics)

    return validate_profile_document(payload, source=source)


def validate_workflow_document(payload: JSONValue, *, source: str = "<memory>") -> ValidationReport:
    """Validate canonical JSON-shaped workflow data."""

    diagnostics: list[Diagnostic] = []

    if not isinstance(payload, dict):
        diagnostics.append(_diagnostic("validation.workflow.root_type", "Workflow root must be an object", (), source, actual_type=type(payload).__name__))
        return ValidationReport(document_kind="workflow", status=RuntimeStatus.VALIDATION_ERROR, diagnostics=tuple(diagnostics))

    diagnostics.extend(_validate_unknown_fields(payload, WORKFLOW_ALLOWED_FIELDS, path=(), source=source))
    diagnostics.extend(_require_exact_int(payload, "version", 0, source=source))
    diagnostics.extend(_require_non_empty_string(payload, "workflow", source=source))
    diagnostics.extend(_require_object_field(payload, "inputs", source=source, required=False))
    diagnostics.extend(_require_object_field(payload, "state_needs", source=source, required=False))
    diagnostics.extend(_validate_workflow_blocks(payload, source=source))

    return _report("workflow", diagnostics)


def _validate_workflow_blocks(payload: JSONObject, *, source: str) -> list[Diagnostic]:
    return _validate_block_list(payload.get("blocks"), source=source)


def _validate_block_list(value: JSONValue | None, *, source: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not isinstance(value, list):
        diagnostics.append(_diagnostic("validation.workflow.blocks.type", "Field 'blocks' must be a list", ("blocks",), source, actual_type=type(value).__name__))
        return diagnostics

    declared_registers = _collect_declared_registers_from_blocks(value)
    seen_registers: dict[str, tuple[str, ...]] = {}
    for index, item in enumerate(value):
        path = ("blocks", str(index))
        if not isinstance(item, dict):
            diagnostics.append(_diagnostic("validation.workflow.block.type", "Block entry must be an object", path, source, actual_type=type(item).__name__))
            continue
        diagnostics.extend(_validate_unknown_fields(item, BLOCK_ALLOWED_FIELDS, path=path, source=source))
        has_guards = "guards" in item
        has_steps = "steps" in item
        if has_guards == has_steps:
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.block.form",
                    "Block must define exactly one of 'guards' or 'steps'",
                    path,
                    source,
                )
            )
            continue
        if has_guards:
            diagnostics.extend(_validate_guard_list(item.get("guards"), source=source, path=path + ("guards",)))
        else:
            step_path = path + ("steps",)
            diagnostics.extend(
                _validate_step_list(
                    item.get("steps"),
                    source=source,
                    path=step_path,
                    prior_registers=seen_registers,
                    declared_registers=declared_registers,
                )
            )
            seen_registers.update(_collect_declared_registers_from_step_list(item.get("steps"), path=step_path))
    return diagnostics


def _collect_declared_registers_from_blocks(value: list[JSONValue]) -> dict[str, tuple[str, ...]]:
    declared_registers: dict[str, tuple[str, ...]] = {}
    for index, item in enumerate(value):
        if not isinstance(item, dict) or "steps" not in item:
            continue
        declared_registers.update(_collect_declared_registers_from_step_list(item.get("steps"), path=("blocks", str(index), "steps")))
    return declared_registers


def _collect_declared_registers_from_step_list(value: JSONValue | None, *, path: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, list):
        return {}
    return {
        item["register"]: path + (str(index), "register")
        for index, item in enumerate(value)
        if isinstance(item, dict)
        and ("uses" in item or "value" in item)
        and isinstance(item.get("register"), str)
        and REGISTER_PATTERN.fullmatch(item["register"])
    }


def validate_profile_document(payload: JSONValue, *, source: str = "<memory>") -> ValidationReport:
    """Validate canonical JSON-shaped profile data."""

    diagnostics: list[Diagnostic] = []

    if not isinstance(payload, dict):
        diagnostics.append(_diagnostic("validation.profile.root_type", "Profile root must be an object", (), source, actual_type=type(payload).__name__))
        return ValidationReport(document_kind="profile", status=RuntimeStatus.VALIDATION_ERROR, diagnostics=tuple(diagnostics))

    diagnostics.extend(_validate_unknown_fields(payload, PROFILE_ALLOWED_FIELDS, path=(), source=source))
    diagnostics.extend(_require_non_empty_string(payload, "name", source=source))
    diagnostics.extend(_require_object_field(payload, "inputs", source=source, required=False))
    diagnostics.extend(_validate_checks(payload.get("checks"), source=source))
    diagnostics.extend(_validate_overrides(payload.get("overrides"), source=source))

    return _report("profile", diagnostics)


def _validate_guard_list(value: JSONValue | None, *, source: str, path: tuple[str, ...] = ("guards",)) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not isinstance(value, list):
        diagnostics.append(_diagnostic("validation.workflow.guards.type", "Field 'guards' must be a list", path, source, actual_type=type(value).__name__))
        return diagnostics

    for index, item in enumerate(value):
        item_path = path + (str(index),)
        if isinstance(item, str):
            if not item:
                diagnostics.append(_diagnostic("validation.workflow.guard_expr.empty", "Guard expression must not be empty", item_path, source))
                continue
            try:
                parsed = parse_guard_expression(item)
            except GuardExpressionParseError as exc:
                diagnostics.append(exc.to_diagnostic(path=item_path, source=source, expression=item))
                continue
            for validation_error in validate_parsed_guard_expression(parsed):
                diagnostics.append(validation_error.to_diagnostic(path=item_path, source=source, expression=item))
            continue
        diagnostics.extend(_validate_call(item, path=item_path, source=source))
    return diagnostics


def _validate_step_list(
    value: JSONValue | None,
    *,
    source: str,
    path: tuple[str, ...] = ("steps",),
    prior_registers: dict[str, tuple[str, ...]] | None = None,
    declared_registers: dict[str, tuple[str, ...]] | None = None,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not isinstance(value, list):
        diagnostics.append(_diagnostic("validation.workflow.steps.type", "Field 'steps' must be a list", path, source, actual_type=type(value).__name__))
        return diagnostics

    seen_names: dict[str, tuple[str, ...]] = {}
    seen_registers = {} if prior_registers is None else dict(prior_registers)
    effective_declared_registers = declared_registers if declared_registers is not None else _collect_declared_registers_from_step_list(value, path=path)
    for index, item in enumerate(value):
        item_path = path + (str(index),)
        if not isinstance(item, dict):
            diagnostics.append(_diagnostic("validation.workflow.step.type", "Step entry must be an object", item_path, source, actual_type=type(item).__name__))
            continue

        diagnostics.extend(_validate_unknown_fields(item, STEP_ALLOWED_FIELDS, path=item_path, source=source))
        diagnostics.extend(_require_non_empty_string(item, "name", path=item_path + ("name",), source=source))
        has_uses = "uses" in item
        has_value = "value" in item
        has_state_set = "state_set" in item
        has_state_delete = "state_delete" in item
        form_count = sum((has_uses, has_value, has_state_set, has_state_delete))

        prior_registers = {name: register_path for name, register_path in seen_registers.items()}

        if form_count != 1:
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.step.form",
                    "Step must define exactly one of 'uses', 'value', 'state_set', or 'state_delete'",
                    item_path,
                    source,
                )
            )
        elif has_uses:
            diagnostics.extend(
                _validate_call(
                    item,
                    path=item_path,
                    source=source,
                    allowed_fields=STEP_ALLOWED_FIELDS,
                    prior_registers=prior_registers,
                    declared_registers=effective_declared_registers,
                )
            )
        elif has_value:
            diagnostics.extend(
                _validate_runtime_value_surface(
                    item.get("value"),
                    path=item_path + ("value",),
                    source=source,
                    prior_registers=prior_registers,
                    declared_registers=effective_declared_registers,
                )
            )
        elif "with" in item:
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.step.with_without_uses",
                    "Step field 'with' is allowed only together with 'uses'",
                    item_path + ("with",),
                    source,
                )
            )

        diagnostics.extend(
            _validate_step_condition(
                item,
                path=item_path,
                source=source,
                prior_registers=prior_registers,
                declared_registers=effective_declared_registers,
            )
        )
        diagnostics.extend(_validate_step_register(item, path=item_path, source=source, can_register=has_uses or has_value))

        if has_state_set:
            diagnostics.extend(_require_object_field(item, "state_set", path=item_path + ("state_set",), source=source, required=True))
            diagnostics.extend(
                _validate_state_set_shape(
                    item.get("state_set"),
                    path=item_path + ("state_set",),
                    source=source,
                    prior_registers=prior_registers,
                    declared_registers=effective_declared_registers,
                )
            )
        if has_state_delete:
            diagnostics.extend(_require_non_empty_string(item, "state_delete", path=item_path + ("state_delete",), source=source))
            diagnostics.extend(_validate_state_path_text(item.get("state_delete"), path=item_path + ("state_delete",), source=source))

        name = item.get("name")
        if isinstance(name, str) and name:
            if name in seen_names:
                diagnostics.append(_diagnostic("validation.workflow.step.duplicate_name", f"Duplicate step name '{name}'", item_path + ("name",), source, first_seen_path=list(seen_names[name])))
            else:
                seen_names[name] = item_path + ("name",)

        register = item.get("register")
        if isinstance(register, str) and register and (has_uses or has_value) and REGISTER_PATTERN.fullmatch(register):
            if register in seen_registers:
                diagnostics.append(
                    _diagnostic(
                        "validation.workflow.step.duplicate_register",
                        f"Duplicate step register '{register}'",
                        item_path + ("register",),
                        source,
                        first_seen_path=list(seen_registers[register]),
                    )
                )
            else:
                seen_registers[register] = item_path + ("register",)

    return diagnostics


def _validate_step_condition(
    value: JSONObject,
    *,
    path: tuple[str, ...],
    source: str,
    prior_registers: dict[str, tuple[str, ...]] | None = None,
    declared_registers: dict[str, tuple[str, ...]] | None = None,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    condition = value.get("if")
    if condition is None:
        return diagnostics
    condition_path = path + ("if",)
    if not isinstance(condition, str):
        diagnostics.append(
            _diagnostic(
                "validation.workflow.step.if.type",
                "Step field 'if' must be a string-form value expression",
                condition_path,
                source,
                actual_type=type(condition).__name__,
            )
        )
        return diagnostics
    expression = _extract_runtime_value_expression(condition)
    if expression is None:
        diagnostics.append(
            _diagnostic(
                "validation.workflow.step.if.expression",
                "Step field 'if' must use the '${...}' value-expression form",
                condition_path,
                source,
            )
        )
        return diagnostics
    if value.get("register") is not None:
        diagnostics.append(
            _diagnostic(
                "validation.workflow.step.if_with_register",
                "Step fields 'if' and 'register' cannot be used together in the MVP",
                condition_path,
                source,
            )
        )
    try:
        parsed = parse_value_expression(expression)
    except ValueExpressionParseError as exc:
        diagnostics.append(exc.to_diagnostic(path=condition_path, source=source, expression=expression))
        return diagnostics
    diagnostics.extend(
        _validate_step_references(
            collect_step_references(parsed.root),
            path=condition_path,
            source=source,
            prior_registers={} if prior_registers is None else prior_registers,
            declared_registers={} if declared_registers is None else declared_registers,
        )
    )
    diagnostics.extend(_validate_step_condition_type(parsed.root, path=condition_path, source=source))
    return diagnostics


def _validate_step_register(value: JSONObject, *, path: tuple[str, ...], source: str, can_register: bool) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    register = value.get("register")
    if register is None:
        return diagnostics
    if not can_register:
        diagnostics.append(
            _diagnostic(
                "validation.workflow.step.register_without_uses",
                "Step field 'register' is allowed only together with 'uses' or 'value'",
                path + ("register",),
                source,
            )
        )
        return diagnostics
    if not isinstance(register, str):
        diagnostics.append(
            _diagnostic(
                "validation.workflow.step.register.type",
                "Step field 'register' must be a string",
                path + ("register",),
                source,
                actual_type=type(register).__name__,
            )
        )
        return diagnostics
    if not register:
        diagnostics.append(
            _diagnostic(
                "validation.workflow.step.register.empty",
                "Step field 'register' must not be empty",
                path + ("register",),
                source,
            )
        )
        return diagnostics
    if not REGISTER_PATTERN.fullmatch(register):
        diagnostics.append(
            _diagnostic(
                "validation.workflow.step.register.pattern",
                "Step register must match the stable workflow register pattern",
                path + ("register",),
                source,
                pattern=REGISTER_PATTERN.pattern,
            )
        )
    return diagnostics


def _validate_call(
    value: JSONValue,
    *,
    path: tuple[str, ...],
    source: str,
    allowed_fields: frozenset[str] = CALL_ALLOWED_FIELDS,
    prior_registers: dict[str, tuple[str, ...]] | None = None,
    declared_registers: dict[str, tuple[str, ...]] | None = None,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not isinstance(value, dict):
        diagnostics.append(_diagnostic("validation.workflow.call.type", "Operation entry must be an object", path, source, actual_type=type(value).__name__))
        return diagnostics

    if allowed_fields is CALL_ALLOWED_FIELDS:
        diagnostics.extend(_validate_unknown_fields(value, CALL_ALLOWED_FIELDS, path=path, source=source))

    diagnostics.extend(_require_non_empty_string(value, "uses", path=path + ("uses",), source=source, pattern=USES_PATTERN, pattern_message="Operation reference must match the stable connector operation pattern"))
    diagnostics.extend(_require_object_field(value, "with", path=path + ("with",), source=source, required=False))
    with_payload = value.get("with")
    if isinstance(with_payload, dict):
        diagnostics.extend(
            _validate_runtime_value_surface(
                with_payload,
                path=path + ("with",),
                source=source,
                prior_registers=prior_registers,
                declared_registers=declared_registers,
            )
        )
    return diagnostics


def _validate_state_set_shape(
    value: JSONValue | None,
    *,
    path: tuple[str, ...],
    source: str,
    prior_registers: dict[str, tuple[str, ...]] | None = None,
    declared_registers: dict[str, tuple[str, ...]] | None = None,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not isinstance(value, dict):
        return diagnostics
    if len(value) != 1:
        diagnostics.append(
            _diagnostic(
                "validation.workflow.state_set.entry_count",
                "Field 'state_set' must contain exactly one target entry",
                path,
                source,
                actual_count=len(value),
            )
        )
    for key in value:
        if not isinstance(key, str) or not key:
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.state_set.target_type",
                    "State set target must be a non-empty string",
                    path,
                    source,
                    actual_type=type(key).__name__,
                )
            )
            continue
        diagnostics.extend(_validate_state_path_text(key, path=path + (key,), source=source))
    for key, item in value.items():
        if isinstance(key, str):
            diagnostics.extend(
                _validate_runtime_value_surface(
                    item,
                    path=path + (key,),
                    source=source,
                    prior_registers=prior_registers,
                    declared_registers=declared_registers,
                )
            )
    return diagnostics


def _validate_runtime_value_surface(
    value: JSONValue | None,
    *,
    path: tuple[str, ...],
    source: str,
    prior_registers: dict[str, tuple[str, ...]] | None = None,
    declared_registers: dict[str, tuple[str, ...]] | None = None,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if _is_format_value_object(value):
        diagnostics.extend(
            _validate_format_value_object(
                value,
                path=path,
                source=source,
                prior_registers=prior_registers,
                declared_registers=declared_registers,
            )
        )
        return diagnostics
    if isinstance(value, list):
        for index, item in enumerate(value):
            diagnostics.extend(
                _validate_runtime_value_surface(
                    item,
                    path=path + (str(index),),
                    source=source,
                    prior_registers=prior_registers,
                    declared_registers=declared_registers,
                )
            )
        return diagnostics
    if isinstance(value, dict):
        for key, item in value.items():
            diagnostics.extend(
                _validate_runtime_value_surface(
                    item,
                    path=path + (str(key),),
                    source=source,
                    prior_registers=prior_registers,
                    declared_registers=declared_registers,
                )
            )
        return diagnostics
    if not isinstance(value, str):
        return diagnostics
    expression = _extract_runtime_value_expression(value)
    if expression is None:
        return diagnostics
    try:
        parsed = parse_value_expression(expression)
    except ValueExpressionParseError as exc:
        diagnostics.append(exc.to_diagnostic(path=path, source=source, expression=expression))
        return diagnostics
    diagnostics.extend(
        _validate_step_references(
            collect_step_references(parsed.root),
            path=path,
            source=source,
            prior_registers={} if prior_registers is None else prior_registers,
            declared_registers={} if declared_registers is None else declared_registers,
        )
    )
    return diagnostics


def _extract_runtime_value_expression(value: str) -> str | None:
    if value.startswith("${") and value.endswith("}") and len(value) >= 4:
        return value[2:-1]
    return None


def _validate_step_condition_type(node: ValueExpressionNode, *, path: tuple[str, ...], source: str) -> list[Diagnostic]:
    inferred, diagnostics = _infer_value_expression_type(node, path=path, source=source)
    if inferred not in {"boolean", "unknown"}:
        diagnostics.append(
            _diagnostic(
                "validation.workflow.step.if_expr.result_type",
                "Step condition must evaluate to a boolean value",
                path,
                source,
                inferred_type=inferred,
            )
        )
    return diagnostics


def _infer_value_expression_type(
    node: ValueExpressionNode,
    *,
    path: tuple[str, ...],
    source: str,
) -> tuple[str, list[Diagnostic]]:
    diagnostics: list[Diagnostic] = []
    if isinstance(node, LiteralNode):
        if isinstance(node.value, bool):
            return "boolean", diagnostics
        if isinstance(node.value, str):
            return "string", diagnostics
        if isinstance(node.value, int):
            return "integer", diagnostics
        if node.value is None:
            return "null", diagnostics
        return "unknown", diagnostics
    if isinstance(node, (ReferenceNode, StateReferenceNode, StepReferenceNode)):
        return "unknown", diagnostics
    if isinstance(node, BuiltinCallNode):
        if node.name == "format":
            return "string", diagnostics
        return "unknown", diagnostics
    if isinstance(node, PipelineNode):
        current_type, diagnostics = _infer_value_expression_type(node.source, path=path, source=source)
        for filter_node in node.filters:
            current_type, filter_diagnostics = _infer_filter_result_type(filter_node, input_type=current_type, path=path, source=source)
            diagnostics.extend(filter_diagnostics)
        return current_type, diagnostics
    return "unknown", diagnostics


def _infer_filter_result_type(
    filter_node: FilterApplicationNode,
    *,
    input_type: str,
    path: tuple[str, ...],
    source: str,
) -> tuple[str, list[Diagnostic]]:
    diagnostics: list[Diagnostic] = []
    if filter_node.name in {"lower", "trim", "slug"}:
        if filter_node.arguments:
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.step.if_expr.filter_args",
                    f"Filter '{filter_node.name}' does not accept arguments",
                    path,
                    source,
                    filter=filter_node.name,
                    arguments=len(filter_node.arguments),
                )
            )
        if input_type not in {"string", "unknown"}:
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.step.if_expr.filter_type",
                    f"Filter '{filter_node.name}' requires a string input",
                    path,
                    source,
                    filter=filter_node.name,
                    actual_type=input_type,
                )
            )
        return "string", diagnostics
    if filter_node.name in {"eq", "ne"}:
        if len(filter_node.arguments) != 1:
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.step.if_expr.filter_args",
                    f"Filter '{filter_node.name}' requires exactly one argument",
                    path,
                    source,
                    filter=filter_node.name,
                    arguments=len(filter_node.arguments),
                )
            )
        return "boolean", diagnostics
    if filter_node.name == "not":
        if filter_node.arguments:
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.step.if_expr.filter_args",
                    "Filter 'not' does not accept arguments",
                    path,
                    source,
                    filter="not",
                    arguments=len(filter_node.arguments),
                )
            )
        if input_type not in {"boolean", "unknown"}:
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.step.if_expr.not_type",
                    "Filter 'not' requires a boolean input",
                    path,
                    source,
                    actual_type=input_type,
                )
            )
        return "boolean", diagnostics
    return "unknown", diagnostics


def _is_format_value_object(value: JSONValue | None) -> bool:
    return isinstance(value, dict) and "format" in value


def _validate_format_value_object(
    value: JSONObject,
    *,
    path: tuple[str, ...],
    source: str,
    prior_registers: dict[str, tuple[str, ...]] | None = None,
    declared_registers: dict[str, tuple[str, ...]] | None = None,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    allowed_fields = {"format", "args"}
    for key in value:
        if key not in allowed_fields:
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.value_expr.format.unknown_field",
                    f"Unknown value-expression format field '{key}'",
                    path + (key,),
                    source,
                    allowed_fields=sorted(allowed_fields),
                )
            )
    template = value.get("format")
    if not isinstance(template, str):
        diagnostics.append(
            _diagnostic(
                "validation.workflow.value_expr.format.template_type",
                "Field 'format' must be a string",
                path + ("format",),
                source,
                actual_type=type(template).__name__,
            )
        )
    args = value.get("args", [])
    if not isinstance(args, list):
        diagnostics.append(
            _diagnostic(
                "validation.workflow.value_expr.format.args_type",
                "Field 'args' must be a list when provided",
                path + ("args",),
                source,
                actual_type=type(args).__name__,
            )
        )
        return diagnostics
    for index, item in enumerate(args):
        diagnostics.extend(
            _validate_runtime_value_surface(
                item,
                path=path + ("args", str(index)),
                source=source,
                prior_registers=prior_registers,
                declared_registers=declared_registers,
            )
        )
    return diagnostics


def _validate_step_references(
    references: tuple[StepReferenceNode, ...],
    *,
    path: tuple[str, ...],
    source: str,
    prior_registers: dict[str, tuple[str, ...]],
    declared_registers: dict[str, tuple[str, ...]],
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for reference in references:
        if not reference.fields or reference.fields[0] not in {"status", "summary", "outputs"}:
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.step_ref.surface",
                    "Registered step references must use status, summary, or outputs as the first field",
                    path,
                    source,
                    register=reference.register,
                    fields=list(reference.fields),
                )
            )
            continue
        if reference.register in prior_registers:
            continue
        if reference.register in declared_registers:
            diagnostics.append(
                _diagnostic(
                    "validation.workflow.step_ref.forward",
                    f"Registered step '{reference.register}' must be declared by an earlier step",
                    path,
                    source,
                    register=reference.register,
                    declared_at=list(declared_registers[reference.register]),
                )
            )
            continue
        diagnostics.append(
            _diagnostic(
                "validation.workflow.step_ref.unknown",
                f"Registered step '{reference.register}' is not declared in this workflow",
                path,
                source,
                register=reference.register,
            )
        )
    return diagnostics


def _validate_state_path_text(value: JSONValue | None, *, path: tuple[str, ...], source: str) -> list[Diagnostic]:
    if not isinstance(value, str) or not value:
        return []
    try:
        parse_state_path(value)
    except StatePathParseError as exc:
        return [exc.to_diagnostic(path=path, source=source, expression=value)]
    return []


def _validate_checks(value: JSONValue | None, *, source: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if value is None:
        return diagnostics
    if not isinstance(value, list):
        diagnostics.append(_diagnostic("validation.profile.checks.type", "Field 'checks' must be a list", ("checks",), source, actual_type=type(value).__name__))
        return diagnostics

    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            diagnostics.append(_diagnostic("validation.profile.checks.item_type", "Check entries must be non-empty strings", ("checks", str(index)), source, actual_type=type(item).__name__))
    return diagnostics


def _validate_overrides(value: JSONValue | None, *, source: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if value is None:
        return diagnostics
    if not isinstance(value, list):
        diagnostics.append(_diagnostic("validation.profile.overrides.type", "Field 'overrides' must be a list", ("overrides",), source, actual_type=type(value).__name__))
        return diagnostics

    seen_targets: dict[str, tuple[str, ...]] = {}
    for index, item in enumerate(value):
        path = ("overrides", str(index))
        if not isinstance(item, dict):
            diagnostics.append(_diagnostic("validation.profile.override.type", "Override entry must be an object", path, source, actual_type=type(item).__name__))
            continue

        diagnostics.extend(_validate_unknown_fields(item, OVERRIDE_ALLOWED_FIELDS, path=path, source=source))
        diagnostics.extend(_require_non_empty_string(item, "target", path=path + ("target",), source=source, pattern=USES_PATTERN, pattern_message="Override target must match the stable operation reference pattern"))
        diagnostics.extend(_require_object_field(item, "with", path=path + ("with",), source=source, required=False))

        reason = item.get("reason")
        if reason is not None and (not isinstance(reason, str) or not reason):
            diagnostics.append(_diagnostic("validation.profile.override.reason_type", "Override reason must be a non-empty string when provided", path + ("reason",), source, actual_type=type(reason).__name__))

        target = item.get("target")
        if isinstance(target, str) and target:
            if target in seen_targets:
                diagnostics.append(_diagnostic("validation.profile.override.duplicate_target", f"Duplicate override target '{target}'", path + ("target",), source, first_seen_path=list(seen_targets[target])))
            else:
                seen_targets[target] = path + ("target",)

    return diagnostics


def _validate_unknown_fields(data: JSONObject, allowed: frozenset[str], *, path: tuple[str, ...], source: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for key in data:
        if key not in allowed:
            diagnostics.append(_diagnostic("validation.unknown_field", f"Unknown field '{key}'", path + (key,), source, allowed_fields=sorted(allowed)))
    return diagnostics


def _require_exact_int(data: JSONObject, key: str, expected: int, *, source: str) -> list[Diagnostic]:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return [_diagnostic(f"validation.{key}.type", f"Field '{key}' must be an integer", (key,), source, actual_type=type(value).__name__)]
    if value != expected:
        return [_diagnostic(f"validation.{key}.value", f"Field '{key}' must equal {expected}", (key,), source, actual_value=value)]
    return []


def _require_non_empty_string(
    data: JSONObject,
    key: str,
    *,
    source: str,
    path: tuple[str, ...] | None = None,
    pattern: re.Pattern[str] | None = None,
    pattern_message: str | None = None,
) -> list[Diagnostic]:
    value = data.get(key)
    result_path = path or (key,)
    if not isinstance(value, str):
        return [_diagnostic(f"validation.{key}.type", f"Field '{key}' must be a string", result_path, source, actual_type=type(value).__name__)]
    if not value:
        return [_diagnostic(f"validation.{key}.empty", f"Field '{key}' must not be empty", result_path, source)]
    if pattern is not None and pattern.fullmatch(value) is None:
        return [_diagnostic(f"validation.{key}.pattern", pattern_message or f"Field '{key}' has invalid format", result_path, source, actual_value=value)]
    return []


def _require_object_field(
    data: JSONObject,
    key: str,
    *,
    source: str,
    path: tuple[str, ...] | None = None,
    required: bool,
) -> list[Diagnostic]:
    if key not in data:
        return [] if not required else [_diagnostic(f"validation.{key}.missing", f"Field '{key}' is required", path or (key,), source)]
    value = data[key]
    if not isinstance(value, dict):
        return [_diagnostic(f"validation.{key}.type", f"Field '{key}' must be an object", path or (key,), source, actual_type=type(value).__name__)]
    return []


def _diagnostic(code: str, message: str, path: tuple[str, ...], source: str, **details: object) -> Diagnostic:
    payload = {"source": source, **details}
    return Diagnostic(code=code, level="error", message=message, path=path, details=payload)


def _report(document_kind: str, diagnostics: list[Diagnostic]) -> ValidationReport:
    if diagnostics:
        return ValidationReport(document_kind=document_kind, status=RuntimeStatus.VALIDATION_ERROR, diagnostics=tuple(diagnostics))
    return ValidationReport(document_kind=document_kind, status=RuntimeStatus.OK, diagnostics=())
