"""YAML loading into canonical JSON-shaped models and local-expression-aware workflow assembly."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import yaml

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONArray, JSONObject, JSONScalar, JSONValue
from ordo.model.launcher import Launcher
from ordo.model.profile import Override, Profile
from ordo.model.workflow import Guard, GuardBlock, OperationRef, Step, StepBlock, Workflow, WorkflowBlock
from ordo.runtime.local_expression_contexts import LocalExpressionContext
from ordo.runtime.local_expressions import LOCAL_EXPRESSION_PARSE_ERRORS, parse_embedded_local_expression
from ordo.runtime.local_expression_engine.core import BinaryNode, BuiltinCallNode, FilterApplicationNode, LocalExpressionNode, ParsedLocalExpressionTree, PipelineNode, ReferenceNode, StateReferenceNode, StepReferenceNode, UnaryNode, parse_local_expression_tree


@dataclass(frozen=True, slots=True)
class LoadError(Exception):
    """Structured loader error suitable for diagnostics."""

    diagnostics: tuple[Diagnostic, ...]

    def __str__(self) -> str:
        return "; ".join(diagnostic.message for diagnostic in self.diagnostics)


@dataclass(frozen=True, slots=True)
class FragmentArgSpec:
    """Canonical included-fragment argument declaration."""

    type_name: str
    required: bool
    has_default: bool
    default_value: JSONValue | None = None

    @property
    def allows_null_binding(self) -> bool:
        return self.type_name == "null" or (self.has_default and self.default_value is None)


@dataclass(frozen=True, slots=True)
class _BoundFragmentExpression:
    """Internal string value that preserves caller-side step-binding provenance."""

    text: str
    allowed_caller_step_refs: frozenset[str] = frozenset()


def load_workflow_text(text: str, *, source: str = "<memory>") -> Workflow:
    """Load workflow YAML into the canonical typed model."""

    payload = load_yaml_document(text, source=source)
    if not isinstance(payload, dict):
        raise _load_error(
            code="load.workflow.root_type",
            message="Workflow root must be a mapping",
            path=(),
            details={"source": source, "actual_type": type(payload).__name__},
        )

    return load_workflow_payload(payload, source=source)


def load_workflow_file(path: str | Path, *, launch_dir: str | Path | None = None) -> Workflow:
    """Load workflow YAML from a file path."""

    workflow_path = Path(path)
    source = str(workflow_path)
    payload = load_workflow_document_file(workflow_path, launch_dir=launch_dir)
    return load_workflow_payload(payload, source=source, launch_dir=launch_dir)


def load_workflow_payload(payload: JSONObject, *, source: str, launch_dir: str | Path | None = None) -> Workflow:
    """Load one already-expanded workflow payload into the canonical typed model."""

    blocks = _load_workflow_blocks(payload, source=source)
    workflow_inputs, declared_inputs = _load_workflow_inputs(payload, source=source)
    let_bindings = _load_workflow_let_bindings(payload, source=source)
    resolved_launch_dir = None if launch_dir is None else _resolve_launch_directory(launch_dir)
    return Workflow(
        version=_require_int(payload, "version", source=source),
        workflow=_require_string(payload, "workflow", source=source),
        inputs=workflow_inputs,
        declared_inputs=declared_inputs,
        let_bindings=let_bindings,
        state_needs=_optional_object(payload, "state_needs", source=source),
        state_bindings=_optional_object(payload, "state_bindings", source=source),
        states=_optional_object(payload, "states", source=source),
        blocks=blocks,
        source_path=None if source == "<memory>" else source,
        launch_dir=None if resolved_launch_dir is None else str(resolved_launch_dir),
    )


def load_workflow_document_file(path: str | Path, *, launch_dir: str | Path | None = None) -> JSONObject:
    """Load one workflow document and expand include directives."""

    workflow_path = Path(path).resolve()
    entry_launch_dir = _resolve_launch_directory(launch_dir)
    return _expand_workflow_includes(workflow_path, launch_dir=entry_launch_dir, stack=(), depth=0)


def load_profile_text(text: str, *, source: str = "<memory>") -> Profile:
    """Load profile YAML into the canonical typed model."""

    payload = load_yaml_document(text, source=source)
    if not isinstance(payload, dict):
        raise _load_error(
            code="load.profile.root_type",
            message="Profile root must be a mapping",
            path=(),
            details={"source": source, "actual_type": type(payload).__name__},
        )

    overrides_data = payload.get("overrides", [])
    if not isinstance(overrides_data, list):
        raise _load_error(
            code="load.profile.overrides_type",
            message="Profile overrides must be a list",
            path=("overrides",),
            details={"source": source, "actual_type": type(overrides_data).__name__},
        )

    checks_data = payload.get("checks", [])
    if not isinstance(checks_data, list):
        raise _load_error(
            code="load.profile.checks_type",
            message="Profile checks must be a list",
            path=("checks",),
            details={"source": source, "actual_type": type(checks_data).__name__},
        )

    return Profile(
        name=_require_string(payload, "name", source=source),
        inputs=_optional_object(payload, "inputs", source=source),
        working_directory=_optional_string(payload, "working_directory", source=source),
        checks=tuple(_require_string_item(item, path=("checks", str(index)), source=source) for index, item in enumerate(checks_data)),
        overrides=tuple(_load_override(item, index=index, source=source) for index, item in enumerate(overrides_data)),
        launchers=_load_launchers(payload.get("launchers"), source=source),
    )


def load_profile_file(path: str | Path) -> Profile:
    """Load profile YAML from a file path."""

    source = str(path)
    return load_profile_text(Path(path).read_text(encoding="utf-8"), source=source)


def load_yaml_document(text: str, *, source: str = "<memory>") -> JSONValue:
    """Load YAML and normalize it into canonical JSON-shaped data."""

    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        details: JSONObject = {"source": source}
        if mark is not None:
            details["line"] = mark.line + 1
            details["column"] = mark.column + 1
        raise _load_error(
            code="load.yaml.syntax",
            message="Invalid YAML document",
            path=(),
            details=details,
        ) from exc

    return _normalize_json_value(loaded, source=source, path=())


MAX_WORKFLOW_INCLUDE_DEPTH = 32
WORKFLOW_INCLUDE_BUILTIN_DIR = Path(__file__).resolve().parents[1] / "includes"


def _expand_workflow_includes(
    path: Path,
    *,
    launch_dir: Path,
    stack: tuple[Path, ...],
    depth: int,
) -> JSONObject:
    resolved_path = path.resolve()
    if resolved_path in stack:
        raise _workflow_include_error(
            code="load.workflow.include.cycle",
            message="Workflow include cycle detected",
            include_path=("include",),
            include_chain=stack + (resolved_path,),
            source=str(resolved_path),
        )
    if depth >= MAX_WORKFLOW_INCLUDE_DEPTH:
        raise _workflow_include_error(
            code="load.workflow.include.depth",
            message="Workflow include depth limit exceeded",
            include_path=("include",),
            include_chain=stack + (resolved_path,),
            source=str(resolved_path),
            max_depth=MAX_WORKFLOW_INCLUDE_DEPTH,
        )

    try:
        payload = load_yaml_document(resolved_path.read_text(encoding="utf-8"), source=str(resolved_path))
    except FileNotFoundError as exc:
        raise _workflow_include_error(
            code="load.workflow.include.not_found",
            message="Workflow include file does not exist",
            include_path=("include",),
            include_chain=stack + (resolved_path,),
            source=str(resolved_path),
        ) from exc

    if not isinstance(payload, dict):
        raise _workflow_include_error(
            code="load.workflow.root_type",
            message="Workflow root must be a mapping",
            include_path=(),
            include_chain=stack + (resolved_path,),
            source=str(resolved_path),
            actual_type=type(payload).__name__,
        )

    return _expand_include_nodes(payload, current_file=resolved_path, launch_dir=launch_dir, stack=stack + (resolved_path,), depth=depth)


def _expand_include_nodes(
    value: JSONValue,
    *,
    current_file: Path,
    launch_dir: Path,
    stack: tuple[Path, ...],
    depth: int,
    current_path: tuple[str, ...] = (),
) -> JSONValue:
    if isinstance(value, list):
        expanded: list[JSONValue] = []
        for index, item in enumerate(value):
            item_value = _expand_include_nodes(item, current_file=current_file, launch_dir=launch_dir, stack=stack, depth=depth, current_path=current_path + (str(index),))
            if isinstance(item_value, list):
                expanded.extend(item_value)
                continue
            expanded.append(item_value)
        return expanded
    if not isinstance(value, dict):
        return value
    if "include" in value:
        if set(value.keys()) - {"include", "with"}:
            raise _workflow_include_error(
                code="load.workflow.include.form",
                message="Include node may contain only 'include' and optional 'with' fields",
                include_path=current_path,
                include_chain=stack,
                source=str(current_file),
            )
        include_ref = value.get("include")
        if not isinstance(include_ref, str) or not include_ref:
            raise _workflow_include_error(
                code="load.workflow.include.type",
                message="Include reference must be a non-empty string",
                include_path=current_path + ("include",),
                include_chain=stack,
                source=str(current_file),
                actual_type=type(include_ref).__name__,
            )
        with_payload = value.get("with")
        if with_payload is None:
            include_bindings: JSONObject = {}
        elif not isinstance(with_payload, dict):
            raise _workflow_include_error(
                code="load.workflow.include.with.type",
                message="Include field 'with' must be an object when provided",
                include_path=current_path + ("with",),
                include_chain=stack,
                source=str(current_file),
                actual_type=type(with_payload).__name__,
            )
        else:
            include_bindings = dict(with_payload)
        include_path = _resolve_include_path(include_ref, current_file=current_file, launch_dir=launch_dir, include_path=current_path + ("include",), stack=stack)
        included_payload = _load_included_fragment_payload(
            include_path,
            launch_dir=launch_dir,
            stack=stack,
            depth=depth + 1,
            include_bindings=include_bindings,
            include_node_path=current_path,
        )
        return included_payload
    if "run" in value:
        rewritten = {
            key: _expand_include_nodes(item, current_file=current_file, launch_dir=launch_dir, stack=stack, depth=depth, current_path=current_path + (key,))
            for key, item in value.items()
        }
        run_ref = rewritten.get("run")
        if isinstance(run_ref, str) and run_ref:
            resolved_run_path = _resolve_include_path(run_ref, current_file=current_file, launch_dir=launch_dir, include_path=current_path + ("run",), stack=stack)
            rewritten["__run_path__"] = str(resolved_run_path)
        return rewritten

    return {
        key: _expand_include_nodes(item, current_file=current_file, launch_dir=launch_dir, stack=stack, depth=depth, current_path=current_path + (key,))
        for key, item in value.items()
    }


def _load_included_fragment_payload(
    path: Path,
    *,
    launch_dir: Path,
    stack: tuple[Path, ...],
    depth: int,
    include_bindings: JSONObject,
    include_node_path: tuple[str, ...],
) -> JSONValue:
    included_payload = _expand_workflow_includes(path, launch_dir=launch_dir, stack=stack, depth=depth)
    fragment_payload = _prepare_included_fragment_payload(
        included_payload,
        source=path,
        include_chain=stack + (path.resolve(),),
        include_bindings=include_bindings,
        include_node_path=include_node_path,
    )
    return _expand_include_nodes(fragment_payload, current_file=path.resolve(), launch_dir=launch_dir, stack=stack + (path.resolve(),), depth=depth)


def _prepare_included_fragment_payload(
    payload: JSONObject,
    *,
    source: Path,
    include_chain: tuple[Path, ...],
    include_bindings: JSONObject,
    include_node_path: tuple[str, ...],
) -> JSONValue:
    description = payload.get("description")
    if description is not None and not isinstance(description, str):
        raise _workflow_include_error(
            code="load.workflow.include.fragment.description_type",
            message="Included fragment field 'description' must be a string when provided",
            include_path=include_node_path + ("description",),
            include_chain=include_chain,
            source=str(source),
            actual_type=type(description).__name__,
        )
    args_value = payload.get("args")
    args_contract = _load_fragment_args_contract(args_value, source=source, include_chain=include_chain, include_node_path=include_node_path)
    effective_bindings = _validate_fragment_arg_bindings(
        args_contract,
        include_bindings,
        source=source,
        include_chain=include_chain,
        include_node_path=include_node_path,
    )

    body = {key: value for key, value in payload.items() if key not in {"description", "args"}}
    bound = _bind_fragment_args(body, args_contract=args_contract, include_bindings=effective_bindings, source=source, include_chain=include_chain, include_node_path=include_node_path)
    scoped = _rewrite_fragment_step_scope(bound, source=source, include_chain=include_chain, include_node_path=include_node_path)
    _ensure_fragment_has_no_state_surface(scoped, source=source, include_chain=include_chain, include_node_path=include_node_path)
    if isinstance(scoped, dict) and "blocks" in scoped and set(scoped.keys()) == {"blocks"} and isinstance(scoped["blocks"], list):
        return scoped["blocks"]
    return scoped


def _load_fragment_args_contract(
    value: JSONValue | None,
    *,
    source: Path,
    include_chain: tuple[Path, ...],
    include_node_path: tuple[str, ...],
) -> dict[str, FragmentArgSpec]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise _workflow_include_error(
            code="load.workflow.include.args.invalid_declaration",
            message="Included fragment field 'args' must be an object when provided",
            include_path=include_node_path + ("args",),
            include_chain=include_chain,
            source=str(source),
            actual_type=type(value).__name__,
        )
    contract: dict[str, FragmentArgSpec] = {}
    for name, declared in value.items():
        if not isinstance(name, str) or not name:
            raise _workflow_include_error(
                code="load.workflow.include.args.invalid_declaration",
                message="Included fragment argument names must be non-empty strings",
                include_path=include_node_path + ("args",),
                include_chain=include_chain,
                source=str(source),
            )
        if isinstance(declared, str) and declared:
            contract[name] = FragmentArgSpec(type_name=declared, required=True, has_default=False)
            continue
        if isinstance(declared, dict):
            contract[name] = _load_fragment_arg_object_spec(
                name,
                declared,
                source=source,
                include_chain=include_chain,
                include_node_path=include_node_path,
            )
            continue
        raise _workflow_include_error(
            code="load.workflow.include.args.invalid_declaration",
            message="Included fragment argument declarations must use a non-empty string or an object contract",
            include_path=include_node_path + ("args", name),
            include_chain=include_chain,
            source=str(source),
            actual_type=type(declared).__name__,
        )
    return contract


def _load_fragment_arg_object_spec(
    name: str,
    declared: JSONObject,
    *,
    source: Path,
    include_chain: tuple[Path, ...],
    include_node_path: tuple[str, ...],
) -> FragmentArgSpec:
    allowed_fields = {"type", "required", "default"}
    unknown = sorted(key for key in declared if key not in allowed_fields)
    if unknown:
        raise _workflow_include_error(
            code="load.workflow.include.args.invalid_declaration",
            message="Included fragment argument object declarations may use only type, required, and default",
            include_path=include_node_path + ("args", name),
            include_chain=include_chain,
            source=str(source),
            unknown_fields=", ".join(unknown),
        )
    declared_type = declared.get("type")
    if not isinstance(declared_type, str) or not declared_type:
        raise _workflow_include_error(
            code="load.workflow.include.args.invalid_declaration",
            message="Included fragment argument object declarations must provide a non-empty string type",
            include_path=include_node_path + ("args", name, "type"),
            include_chain=include_chain,
            source=str(source),
            actual_type=type(declared_type).__name__,
        )
    required_value = declared.get("required")
    has_default = "default" in declared
    if required_value is None:
        required = not has_default
    elif isinstance(required_value, bool):
        required = required_value
    else:
        raise _workflow_include_error(
            code="load.workflow.include.args.invalid_declaration",
            message="Included fragment argument field 'required' must be a boolean when provided",
            include_path=include_node_path + ("args", name, "required"),
            include_chain=include_chain,
            source=str(source),
            actual_type=type(required_value).__name__,
        )
    if has_default and required:
        raise _workflow_include_error(
            code="load.workflow.include.args.invalid_declaration",
            message="Included fragment arguments with a default must not also be required",
            include_path=include_node_path + ("args", name),
            include_chain=include_chain,
            source=str(source),
        )
    default_value = declared.get("default")
    spec = FragmentArgSpec(type_name=declared_type, required=required, has_default=has_default, default_value=default_value)
    if has_default and not _fragment_arg_value_matches_spec(default_value, spec):
        raise _workflow_include_error(
            code="load.workflow.include.args.invalid_declaration",
            message="Included fragment argument default does not match the declared argument type",
            include_path=include_node_path + ("args", name, "default"),
            include_chain=include_chain,
            source=str(source),
            declared_type=declared_type,
            actual_type=type(default_value).__name__,
        )
    return spec


def _validate_fragment_arg_bindings(
    args_contract: dict[str, FragmentArgSpec],
    include_bindings: JSONObject,
    *,
    source: Path,
    include_chain: tuple[Path, ...],
    include_node_path: tuple[str, ...],
) -> JSONObject:
    missing = [name for name, spec in args_contract.items() if spec.required and name not in include_bindings]
    if missing:
        raise _workflow_include_error(
            code="load.workflow.include.args.missing",
            message="Include bindings are missing required fragment arguments",
            include_path=include_node_path + ("with",),
            include_chain=include_chain,
            source=str(source),
            missing_args=", ".join(missing),
        )
    unknown = [name for name in include_bindings if name not in args_contract]
    if unknown:
        raise _workflow_include_error(
            code="load.workflow.include.args.unknown",
            message="Include bindings contain unknown fragment arguments",
            include_path=include_node_path + ("with",),
            include_chain=include_chain,
            source=str(source),
            unknown_args=", ".join(unknown),
        )
    effective_bindings: JSONObject = dict(include_bindings)
    for name, spec in args_contract.items():
        if name not in include_bindings:
            if spec.has_default:
                effective_bindings[name] = spec.default_value
            continue
        actual_value = include_bindings[name]
        if isinstance(actual_value, str) and _extract_runtime_expression(actual_value) is not None:
            continue
        if _fragment_arg_value_matches_spec(actual_value, spec):
            continue
        raise _workflow_include_error(
            code="load.workflow.include.args.type",
            message="Include binding does not match the declared fragment argument type",
            include_path=include_node_path + ("with", name),
            include_chain=include_chain,
            source=str(source),
            declared_type=spec.type_name,
            actual_type=type(actual_value).__name__,
        )
    return effective_bindings


def _fragment_arg_value_matches_spec(value: JSONValue, spec: FragmentArgSpec) -> bool:
    if value is None and spec.allows_null_binding:
        return True
    return _json_value_matches_declared_type(value, spec.type_name)


def _json_value_matches_declared_type(value: JSONValue, declared_type: str) -> bool:
    match declared_type:
        case "string":
            return isinstance(value, str)
        case "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        case "number":
            return (isinstance(value, int) and not isinstance(value, bool)) or isinstance(value, float)
        case "boolean":
            return isinstance(value, bool)
        case "object":
            return isinstance(value, dict)
        case "array":
            return isinstance(value, list)
        case "null":
            return value is None
        case _:
            return True


def _bind_fragment_args(
    value: JSONValue,
    *,
    args_contract: dict[str, str],
    include_bindings: JSONObject,
    source: Path,
    include_chain: tuple[Path, ...],
    include_node_path: tuple[str, ...],
) -> JSONValue | _BoundFragmentExpression:
    if isinstance(value, list):
        return [
            _bind_fragment_args(item, args_contract=args_contract, include_bindings=include_bindings, source=source, include_chain=include_chain, include_node_path=include_node_path)
            for item in value
        ]
    if isinstance(value, dict):
        return {
            key: _bind_fragment_args(item, args_contract=args_contract, include_bindings=include_bindings, source=source, include_chain=include_chain, include_node_path=include_node_path)
            for key, item in value.items()
        }
    if not isinstance(value, str):
        return value
    return _bind_fragment_arg_string(
        value,
        args_contract=args_contract,
        include_bindings=include_bindings,
        source=source,
        include_chain=include_chain,
        include_node_path=include_node_path,
    )


def _bind_fragment_arg_string(
    value: str,
    *,
    args_contract: dict[str, str],
    include_bindings: JSONObject,
    source: Path,
    include_chain: tuple[Path, ...],
    include_node_path: tuple[str, ...],
) -> JSONValue | _BoundFragmentExpression:
    expression = _extract_runtime_expression(value)
    if expression is None:
        return value
    parsed = parse_local_expression_tree(expression, allow_boolean_composition=True)
    direct_arg_name = _direct_fragment_arg_name(parsed)
    if direct_arg_name is not None:
        if direct_arg_name not in include_bindings:
            raise _workflow_include_error(
                code="load.workflow.include.args.missing",
                message="Included fragment references an unbound fragment argument",
                include_path=include_node_path + ("with", direct_arg_name),
                include_chain=include_chain,
                source=str(source),
            )
        return _preserve_fragment_binding_provenance(include_bindings[direct_arg_name])
    replacements, allowed_caller_step_refs = _collect_fragment_arg_expression_replacements(
        parsed,
        include_bindings=include_bindings,
        source=source,
        include_chain=include_chain,
        include_node_path=include_node_path,
    )
    if not replacements:
        return value
    rebound_expression = _apply_expression_replacements(expression, replacements)
    rebound_value = "${" + rebound_expression + "}"
    if allowed_caller_step_refs:
        return _BoundFragmentExpression(text=rebound_value, allowed_caller_step_refs=allowed_caller_step_refs)
    return rebound_value


def _direct_fragment_arg_name(parsed: ParsedLocalExpressionTree) -> str | None:
    node = parsed.root
    if isinstance(node, ReferenceNode) and len(node.parts) == 2 and node.parts[0] == "args":
        return node.parts[1]
    return None


def _collect_fragment_arg_expression_replacements(
    parsed: ParsedLocalExpressionTree,
    *,
    include_bindings: JSONObject,
    source: Path,
    include_chain: tuple[Path, ...],
    include_node_path: tuple[str, ...],
) -> tuple[list[tuple[int, int, str]], frozenset[str]]:
    replacements: list[tuple[int, int, str]] = []
    allowed_caller_step_refs: set[str] = set()
    for node in _walk_value_expression_nodes(parsed.root):
        if not isinstance(node, ReferenceNode):
            continue
        if len(node.parts) != 2 or node.parts[0] != "args":
            continue
        arg_name = node.parts[1]
        if arg_name not in include_bindings:
            raise _workflow_include_error(
                code="load.workflow.include.args.missing",
                message="Included fragment references an unbound fragment argument",
                include_path=include_node_path + ("with", arg_name),
                include_chain=include_chain,
                source=str(source),
            )
        binding_value = include_bindings[arg_name]
        replacements.append((node.start, node.end, _serialize_binding_for_expression(binding_value, source=source, include_chain=include_chain, include_node_path=include_node_path, arg_name=arg_name)))
        allowed_caller_step_refs.update(_collect_caller_step_reference_registers(binding_value))
    return replacements, frozenset(allowed_caller_step_refs)


def _preserve_fragment_binding_provenance(value: JSONValue) -> JSONValue | _BoundFragmentExpression:
    if not isinstance(value, str):
        return value
    allowed_caller_step_refs = _collect_caller_step_reference_registers(value)
    if not allowed_caller_step_refs:
        return value
    return _BoundFragmentExpression(text=value, allowed_caller_step_refs=allowed_caller_step_refs)


def _collect_caller_step_reference_registers(value: JSONValue) -> frozenset[str]:
    if not isinstance(value, str):
        return frozenset()
    try:
        parsed = parse_embedded_local_expression(value, context=LocalExpressionContext.INCLUDE_BINDING)
    except LOCAL_EXPRESSION_PARSE_ERRORS:
        return frozenset()
    if parsed is None or parsed.value is None:
        return frozenset()
    return frozenset(
        node.register
        for node in _walk_value_expression_nodes(parsed.value.root)
        if isinstance(node, StepReferenceNode)
    )


def _serialize_binding_for_expression(
    value: JSONValue,
    *,
    source: Path,
    include_chain: tuple[Path, ...],
    include_node_path: tuple[str, ...],
    arg_name: str,
) -> str:
    if isinstance(value, str):
        expression = _extract_runtime_expression(value)
        if expression is not None:
            return expression
        return json.dumps(value)
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return json.dumps(value)
    raise _workflow_include_error(
        code="load.workflow.include.args.type",
        message="Fragment argument bound inside an expression must resolve to a scalar or embedded-value local expression",
        include_path=include_node_path + ("with", arg_name),
        include_chain=include_chain,
        source=str(source),
        actual_type=type(value).__name__,
    )


def _rewrite_fragment_step_scope(
    value: JSONValue,
    *,
    source: Path,
    include_chain: tuple[Path, ...],
    include_node_path: tuple[str, ...],
) -> JSONValue:
    local_registers = _collect_fragment_declared_registers(value)
    if not local_registers:
        _ensure_fragment_has_no_external_step_references(
            value,
            register_map={},
            source=source,
            include_chain=include_chain,
            include_node_path=include_node_path,
        )
        return _materialize_bound_fragment_values(value)
    scope_token = _fragment_scope_token(include_chain, include_node_path)
    register_map = {name: f"{scope_token}_{name}" for name in local_registers}
    return _rewrite_fragment_scope_value(
        value,
        register_map=register_map,
        source=source,
        include_chain=include_chain,
        include_node_path=include_node_path,
    )


def _ensure_fragment_has_no_state_surface(
    value: JSONValue,
    *,
    source: Path,
    include_chain: tuple[Path, ...],
    include_node_path: tuple[str, ...],
) -> None:
    if isinstance(value, list):
        for index, item in enumerate(value):
            _ensure_fragment_has_no_state_surface(item, source=source, include_chain=include_chain, include_node_path=include_node_path + (str(index),))
        return
    if isinstance(value, dict):
        for key in ("state_needs", "state_bindings", "states", "state_set", "state_delete"):
            if key in value:
                raise _workflow_include_error(
                    code="load.workflow.include.state_forbidden",
                    message="Included fragments must not read, declare, or mutate runtime state",
                    include_path=include_node_path + (key,),
                    include_chain=include_chain,
                    source=str(source),
                )
        for key, item in value.items():
            _ensure_fragment_has_no_state_surface(item, source=source, include_chain=include_chain, include_node_path=include_node_path + (str(key),))
        return
    if not isinstance(value, str):
        return
    expression = _extract_runtime_expression(value)
    if expression is None:
        return
    parsed = parse_local_expression_tree(expression, allow_boolean_composition=True)
    if _value_expression_uses_state(parsed.root):
        raise _workflow_include_error(
            code="load.workflow.include.state_forbidden",
            message="Included fragments must not read, declare, or mutate runtime state",
            include_path=include_node_path,
            include_chain=include_chain,
            source=str(source),
        )


def _value_expression_uses_state(node: LocalExpressionNode) -> bool:
    if isinstance(node, StateReferenceNode):
        return True
    if isinstance(node, PipelineNode):
        if _value_expression_uses_state(node.source):
            return True
        return any(_value_expression_uses_state(argument) for filter_node in node.filters for argument in filter_node.arguments)
    if isinstance(node, BuiltinCallNode):
        return any(_value_expression_uses_state(argument) for argument in node.arguments)
    if isinstance(node, UnaryNode):
        return _value_expression_uses_state(node.operand)
    if isinstance(node, BinaryNode):
        return _value_expression_uses_state(node.left) or _value_expression_uses_state(node.right)
    return False


def _materialize_bound_fragment_values(value: JSONValue | _BoundFragmentExpression) -> JSONValue:
    if isinstance(value, list):
        return [_materialize_bound_fragment_values(item) for item in value]
    if isinstance(value, dict):
        return {key: _materialize_bound_fragment_values(item) for key, item in value.items()}
    if isinstance(value, _BoundFragmentExpression):
        return value.text
    return value


def _collect_fragment_declared_registers(value: JSONValue) -> set[str]:
    registers: set[str] = set()
    if isinstance(value, list):
        for item in value:
            registers.update(_collect_fragment_declared_registers(item))
        return registers
    if not isinstance(value, dict):
        return registers
    register = value.get("register")
    if isinstance(register, str) and register:
        registers.add(register)
    for item in value.values():
        registers.update(_collect_fragment_declared_registers(item))
    return registers


def _fragment_scope_token(include_chain: tuple[Path, ...], include_node_path: tuple[str, ...]) -> str:
    source_token = include_chain[-1].stem.replace("-", "_").replace(".", "_") or "fragment"
    path_token = "_".join(part for part in include_node_path if part.isdigit()) or "root"
    return f"inc_{source_token}_{path_token}"


def _rewrite_fragment_scope_value(
    value: JSONValue | _BoundFragmentExpression,
    *,
    register_map: dict[str, str],
    source: Path,
    include_chain: tuple[Path, ...],
    include_node_path: tuple[str, ...],
) -> JSONValue:
    if isinstance(value, list):
        return [
            _rewrite_fragment_scope_value(item, register_map=register_map, source=source, include_chain=include_chain, include_node_path=include_node_path)
            for item in value
        ]
    if isinstance(value, dict):
        rewritten: JSONObject = {}
        for key, item in value.items():
            if key == "register" and isinstance(item, str) and item in register_map:
                rewritten[key] = register_map[item]
                continue
            rewritten[key] = _rewrite_fragment_scope_value(item, register_map=register_map, source=source, include_chain=include_chain, include_node_path=include_node_path)
        return rewritten
    if isinstance(value, _BoundFragmentExpression):
        return _rewrite_fragment_step_reference_string(
            value.text,
            register_map=register_map,
            allowed_caller_step_refs=value.allowed_caller_step_refs,
            source=source,
            include_chain=include_chain,
            include_node_path=include_node_path,
        )
    if not isinstance(value, str):
        return value
    return _rewrite_fragment_step_reference_string(
        value,
        register_map=register_map,
        allowed_caller_step_refs=frozenset(),
        source=source,
        include_chain=include_chain,
        include_node_path=include_node_path,
    )


def _rewrite_fragment_step_reference_string(
    value: str,
    *,
    register_map: dict[str, str],
    allowed_caller_step_refs: frozenset[str],
    source: Path,
    include_chain: tuple[Path, ...],
    include_node_path: tuple[str, ...],
) -> str:
    expression = _extract_runtime_expression(value)
    if expression is None:
        return value
    parsed = parse_local_expression_tree(expression, allow_boolean_composition=True)
    replacements: list[tuple[int, int, str]] = []
    for node in _walk_value_expression_nodes(parsed.root):
        if not isinstance(node, StepReferenceNode):
            continue
        if node.register in allowed_caller_step_refs:
            continue
        if node.register not in register_map:
            raise _workflow_include_error(
                code="load.workflow.include.step_scope",
                message="Included fragments must not reference caller-local step registers",
                include_path=include_node_path,
                include_chain=include_chain,
                source=str(source),
                register=node.register,
            )
        rewritten = "step." + register_map[node.register]
        if node.fields:
            rewritten += "." + ".".join(node.fields)
        replacements.append((node.start, node.end, rewritten))
    if not replacements:
        return value
    rebound_expression = _apply_expression_replacements(expression, replacements)
    return "${" + rebound_expression + "}"


def _ensure_fragment_has_no_external_step_references(
    value: JSONValue | _BoundFragmentExpression,
    *,
    register_map: dict[str, str],
    source: Path,
    include_chain: tuple[Path, ...],
    include_node_path: tuple[str, ...],
) -> None:
    if isinstance(value, list):
        for item in value:
            _ensure_fragment_has_no_external_step_references(
                item,
                register_map=register_map,
                source=source,
                include_chain=include_chain,
                include_node_path=include_node_path,
            )
        return
    if isinstance(value, dict):
        for item in value.values():
            _ensure_fragment_has_no_external_step_references(
                item,
                register_map=register_map,
                source=source,
                include_chain=include_chain,
                include_node_path=include_node_path,
            )
        return
    if isinstance(value, _BoundFragmentExpression):
        _rewrite_fragment_step_reference_string(
            value.text,
            register_map=register_map,
            allowed_caller_step_refs=value.allowed_caller_step_refs,
            source=source,
            include_chain=include_chain,
            include_node_path=include_node_path,
        )
        return
    if not isinstance(value, str):
        return
    _rewrite_fragment_step_reference_string(
        value,
        register_map=register_map,
        allowed_caller_step_refs=frozenset(),
        source=source,
        include_chain=include_chain,
        include_node_path=include_node_path,
    )


def _walk_value_expression_nodes(node: LocalExpressionNode) -> list[LocalExpressionNode]:
    nodes = [node]
    if isinstance(node, PipelineNode):
        nodes.extend(_walk_value_expression_nodes(node.source))
        for item in node.filters:
            nodes.extend(_walk_value_expression_nodes(item))
        return nodes
    if isinstance(node, FilterApplicationNode):
        for item in node.arguments:
            nodes.extend(_walk_value_expression_nodes(item))
        return nodes
    if isinstance(node, BuiltinCallNode):
        for item in node.arguments:
            nodes.extend(_walk_value_expression_nodes(item))
        return nodes
    if isinstance(node, UnaryNode):
        nodes.extend(_walk_value_expression_nodes(node.operand))
        return nodes
    if isinstance(node, BinaryNode):
        nodes.extend(_walk_value_expression_nodes(node.left))
        nodes.extend(_walk_value_expression_nodes(node.right))
        return nodes
    return nodes


def _apply_expression_replacements(expression: str, replacements: list[tuple[int, int, str]]) -> str:
    rewritten = expression
    for start, end, replacement in sorted(replacements, key=lambda item: item[0], reverse=True):
        rewritten = rewritten[:start] + replacement + rewritten[end:]
    return rewritten


def _extract_runtime_expression(value: str) -> str | None:
    if value.startswith("${") and value.endswith("}") and len(value) >= 4:
        return value[2:-1]
    return None


def _resolve_include_path(
    include_ref: str,
    *,
    current_file: Path,
    launch_dir: Path,
    include_path: tuple[str, ...],
    stack: tuple[Path, ...],
) -> Path:
    include_candidate = Path(include_ref)
    if include_candidate.is_absolute() or _looks_like_windows_absolute_path(include_ref):
        raise _workflow_include_error(
            code="load.workflow.include.forbidden_path",
            message="Workflow include path must be relative",
            include_path=include_path,
            include_chain=stack,
            source=str(current_file),
            include=include_ref,
        )
    if any(part == ".." for part in include_candidate.parts):
        raise _workflow_include_error(
            code="load.workflow.include.forbidden_path",
            message="Workflow include path must not traverse upward",
            include_path=include_path,
            include_chain=stack,
            source=str(current_file),
            include=include_ref,
        )

    for root in _workflow_include_search_roots(current_file=current_file, launch_dir=launch_dir):
        for candidate in _workflow_include_candidates(root, include_candidate):
            if not candidate.exists():
                continue
            if not candidate.is_file():
                raise _workflow_include_error(
                    code="load.workflow.include.not_file",
                    message="Workflow include target must be a file",
                    include_path=include_path,
                    include_chain=stack,
                    source=str(current_file),
                    include=include_ref,
                    resolved_path=str(candidate.resolve()),
                )
            return candidate.resolve()
    raise _workflow_include_error(
        code="load.workflow.include.not_found",
        message="Workflow include target was not found in the configured search locations",
        include_path=include_path,
        include_chain=stack,
        source=str(current_file),
        include=include_ref,
    )


def _workflow_include_search_roots(*, current_file: Path, launch_dir: Path) -> tuple[Path, ...]:
    roots = [
        current_file.parent.resolve(),
        launch_dir.resolve(),
        (launch_dir / ".ordo").resolve(),
        (Path.home() / ".ordo").resolve(),
        WORKFLOW_INCLUDE_BUILTIN_DIR.resolve(),
    ]
    unique: list[Path] = []
    for root in roots:
        if root not in unique:
            unique.append(root)
    return tuple(unique)


def _workflow_include_candidates(root: Path, include_path: Path) -> tuple[Path, ...]:
    if include_path.suffix:
        return (root / include_path,)
    return (root / include_path.with_suffix(".yaml"), root / include_path.with_suffix(".yml"))


def _resolve_launch_directory(launch_dir: str | Path | None) -> Path:
    if launch_dir is None:
        return Path.cwd().resolve()
    return Path(launch_dir).resolve()


def _looks_like_windows_absolute_path(raw: str) -> bool:
    if len(raw) >= 2 and raw[1] == ":" and raw[0].isalpha():
        return True
    return raw.startswith("\\\\")


def _workflow_include_error(
    *,
    code: str,
    message: str,
    include_path: tuple[str, ...],
    include_chain: tuple[Path, ...],
    source: str,
    **details: object,
) -> LoadError:
    diagnostic_details: JSONObject = {
        "source": source,
        "include_chain": [str(item) for item in include_chain],
    }
    for key, value in details.items():
        if value is None or isinstance(value, (str, bool, int, float)):
            diagnostic_details[key] = value
    return _load_error(code=code, message=message, path=include_path, details=diagnostic_details)


def _load_guard(payload: JSONValue, *, index: int, source: str) -> Guard:
    path = ("guards", str(index))
    return _load_guard_at_path(payload, path=path, source=source)


def _load_workflow_inputs(payload: JSONObject, *, source: str) -> tuple[JSONObject, JSONObject]:
    declared_inputs = _optional_object(payload, "inputs", source=source)
    runtime_inputs: JSONObject = {}
    normalized_declarations: JSONObject = {}
    for key, value in declared_inputs.items():
        if isinstance(value, dict):
            normalized_declarations[key] = dict(value)
            continue
        normalized_declarations[key] = {}
        runtime_inputs[key] = value
    return runtime_inputs, normalized_declarations


def _load_guard_at_path(payload: JSONValue, *, path: tuple[str, ...], source: str) -> Guard:
    if isinstance(payload, str):
        return Guard(expr=payload)

    data = _require_object(payload, path=path, source=source)
    return Guard(operation=_load_operation_ref(data, path=path, source=source))


def _load_step(payload: JSONValue, *, index: int, source: str) -> Step:
    path = ("steps", str(index))
    return _load_step_at_path(payload, path=path, source=source)


def _load_step_at_path(payload: JSONValue, *, path: tuple[str, ...], source: str) -> Step:
    data = _require_object(payload, path=path, source=source)
    has_uses = "uses" in data
    has_run = "run" in data
    has_profile_switch = "profile_switch" in data
    has_value = "value" in data
    has_result = "result" in data
    has_publish = "publish" in data
    has_state_set = "state_set" in data
    has_state_delete = "state_delete" in data
    if sum((has_uses, has_run, has_profile_switch, has_value, has_result, has_publish, has_state_set, has_state_delete)) != 1:
        raise _load_error(
            code="load.step.form",
            message="Step must define exactly one of 'uses', 'run', 'profile_switch', 'value', 'result', 'publish', 'state_set', or 'state_delete'",
            path=path,
            details={"source": source},
        )

    state_set = None
    if has_state_set:
        state_set = _require_object(data.get("state_set"), path=path + ("state_set",), source=source)

    state_delete = None
    if has_state_delete:
        state_delete = _require_string(data, "state_delete", path=path + ("state_delete",), source=source)

    run_with_payload = data.get("with", {}) if has_run else {}
    if has_run and not isinstance(run_with_payload, dict):
        raise _load_error(
            code="load.workflow.run.with_type",
            message="Run field 'with' must be an object when provided",
            path=path + ("with",),
            details={"source": source, "actual_type": type(run_with_payload).__name__},
        )

    return Step(
        name=_require_string(data, "name", path=path + ("name",), source=source),
        operation=_load_operation_ref(data, path=path, source=source) if has_uses else None,
        run=_require_string(data, "run", path=path + ("run",), source=source) if has_run else None,
        for_each=data.get("for_each") if has_run and "for_each" in data else None,
        run_with=dict(run_with_payload) if has_run else {},
        profile_switch=data.get("profile_switch") if has_profile_switch else None,
        value=data.get("value") if has_value else None,
        result=data.get("result") if has_result else None,
        publish=data.get("publish") if has_publish else None,
        state_set=state_set,
        state_delete=state_delete,
        if_=_optional_string(data, "if", path=path + ("if",), source=source),
        register=_optional_string(data, "register", path=path + ("register",), source=source),
        launcher=_optional_string(data, "launcher", path=path + ("launcher",), source=source),
        resolved_run_path=_optional_string(data, "__run_path__", path=path + ("__run_path__",), source=source),
    )


def _load_workflow_blocks(payload: JSONObject, *, source: str) -> tuple[WorkflowBlock, ...]:
    raw_blocks = payload.get("blocks")
    if not isinstance(raw_blocks, list):
        raise _load_error(
            code="load.blocks.type",
            message="Field 'blocks' must be a list",
            path=("blocks",),
            details={"source": source, "actual_type": type(raw_blocks).__name__},
        )
    return tuple(_load_block(item, index=index, source=source) for index, item in enumerate(raw_blocks))


_LET_RESERVED_NAMES = frozenset({"inputs", "args", "state", "step"})


def _load_workflow_let_bindings(payload: JSONObject, *, source: str) -> dict[str, str]:
    raw_bindings = payload.get("let")
    if raw_bindings is None:
        return {}
    if not isinstance(raw_bindings, dict):
        raise _load_error(
            code="load.workflow.let.type",
            message="Field 'let' must be an object",
            path=("let",),
            details={"source": source, "actual_type": type(raw_bindings).__name__},
        )

    loaded: dict[str, str] = {}
    for name, expression in raw_bindings.items():
        path = ("let", str(name))
        if not isinstance(name, str) or not name:
            raise _load_error(
                code="load.workflow.let.name",
                message="Workflow let binding names must be non-empty strings",
                path=path,
                details={"source": source},
            )
        if name in _LET_RESERVED_NAMES:
            raise _load_error(
                code="load.workflow.let.reserved_name",
                message=f"Workflow let binding name '{name}' is reserved",
                path=path,
                details={"source": source, "name": name},
            )
        if not isinstance(expression, str):
            raise _load_error(
                code="load.workflow.let.value_type",
                message="Workflow let binding values must be strings",
                path=path,
                details={"source": source, "actual_type": type(expression).__name__, "name": name},
            )
        loaded[name] = expression
    return loaded


def _load_block(payload: JSONValue, *, index: int, source: str) -> WorkflowBlock:
    path = ("blocks", str(index))
    data = _require_object(payload, path=path, source=source)
    has_guards = "guards" in data
    has_steps = "steps" in data
    if has_guards == has_steps:
        raise _load_error(
            code="load.workflow.block.form",
            message="Block must define exactly one of 'guards' or 'steps'",
            path=path,
            details={"source": source},
        )
    if has_guards:
        guards_payload = data.get("guards")
        if not isinstance(guards_payload, list):
            raise _load_error(
                code="load.workflow.block.guards_type",
                message="Block field 'guards' must be a list",
                path=path + ("guards",),
                details={"source": source, "actual_type": type(guards_payload).__name__},
            )
        return GuardBlock(
            guards=tuple(_load_guard_at_path(item, path=path + ("guards", str(item_index)), source=source) for item_index, item in enumerate(guards_payload))
        )

    if has_steps:
        steps_payload = data.get("steps")
        if not isinstance(steps_payload, list):
            raise _load_error(
                code="load.workflow.block.steps_type",
                message="Block field 'steps' must be a list",
                path=path + ("steps",),
                details={"source": source, "actual_type": type(steps_payload).__name__},
            )
        return StepBlock(
            steps=tuple(_load_step_at_path(item, path=path + ("steps", str(item_index)), source=source) for item_index, item in enumerate(steps_payload))
        )

    raise AssertionError("unreachable")


def _load_override(payload: JSONValue, *, index: int, source: str) -> Override:
    data = _require_object(payload, path=("overrides", str(index)), source=source)
    reason = data.get("reason")
    if reason is not None and not isinstance(reason, str):
        raise _load_error(
            code="load.override.reason_type",
            message="Override reason must be a string when provided",
            path=("overrides", str(index), "reason"),
            details={"source": source, "actual_type": type(reason).__name__},
        )

    return Override(
        target=_require_string(data, "target", path=("overrides", str(index), "target"), source=source),
        with_=_optional_object(data, "with", path=("overrides", str(index), "with"), source=source),
        reason=reason,
    )


def _load_launchers(payload: JSONValue | None, *, source: str) -> dict[str, Launcher]:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise _load_error(
            code="load.profile.launchers_type",
            message="Profile launchers must be a mapping",
            path=("launchers",),
            details={"source": source, "actual_type": type(payload).__name__},
        )

    base_dir = _source_directory(source)
    loaded: dict[str, Launcher] = {}
    for name, item in payload.items():
        path = ("launchers", str(name))
        if not isinstance(name, str) or not name:
            raise _load_error(
                code="load.profile.launcher.name",
                message="Launcher names must be non-empty strings",
                path=path,
                details={"source": source},
            )
        if not isinstance(item, dict):
            raise _load_error(
                code="load.profile.launcher.type",
                message="Launcher definition must be a mapping",
                path=path,
                details={"source": source, "actual_type": type(item).__name__},
            )
        data = item
        if "file" in data:
            file_ref = _require_string(data, "file", path=path + ("file",), source=source)
            if base_dir is None:
                raise _load_error(
                    code="load.profile.launcher.file_requires_file_source",
                    message="Launcher file references require a file-backed profile source",
                    path=path + ("file",),
                    details={"source": source},
                )
            launcher_path = (base_dir / file_ref).resolve()
            launcher_payload = load_yaml_document(launcher_path.read_text(encoding="utf-8"), source=str(launcher_path))
            if not isinstance(launcher_payload, dict):
                raise _load_error(
                    code="load.profile.launcher.file_root_type",
                    message="Launcher file root must be a mapping",
                    path=path + ("file",),
                    details={"source": str(launcher_path), "actual_type": type(launcher_payload).__name__},
                )
            data = launcher_payload
        loaded[name] = Launcher(
            connector=_optional_string(data, "connector", path=path + ("connector",), source=source),
            before=_optional_string(data, "before", path=path + ("before",), source=source),
            after=_optional_string(data, "after", path=path + ("after",), source=source),
        )
    return loaded


def _source_directory(source: str) -> Path | None:
    if source == "<memory>":
        return None
    return Path(source).resolve().parent


def _load_operation_ref(data: JSONObject, *, path: tuple[str, ...], source: str) -> OperationRef:
    with_payload = data.get("with", {})
    if not isinstance(with_payload, dict):
        raise _load_error(
            code="load.operation.with_type",
            message="Operation 'with' field must be an object",
            path=path + ("with",),
            details={"source": source, "actual_type": type(with_payload).__name__},
        )

    return OperationRef(
        uses=_require_string(data, "uses", path=path + ("uses",), source=source),
        with_=dict(with_payload),
    )


def _require_object(value: JSONValue, *, path: tuple[str, ...], source: str) -> JSONObject:
    if isinstance(value, dict):
        return value
    raise _load_error(
        code="load.shape.object_required",
        message="Expected object",
        path=path,
        details={"source": source, "actual_type": type(value).__name__},
    )


def _require_list(data: JSONObject, key: str, *, source: str) -> JSONArray:
    value = data.get(key)
    if isinstance(value, list):
        return value
    raise _load_error(
        code=f"load.{key}.type",
        message=f"Field '{key}' must be a list",
        path=(key,),
        details={"source": source, "actual_type": type(value).__name__},
    )


def _optional_object(
    data: JSONObject,
    key: str,
    *,
    path: tuple[str, ...] | None = None,
    source: str,
) -> JSONObject:
    value = data.get(key, {})
    if isinstance(value, dict):
        return dict(value)
    raise _load_error(
        code=f"load.{key}.type",
        message=f"Field '{key}' must be an object",
        path=path or (key,),
        details={"source": source, "actual_type": type(value).__name__},
    )


def _require_int(data: JSONObject, key: str, *, source: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise _load_error(
            code=f"load.{key}.type",
            message=f"Field '{key}' must be an integer",
            path=(key,),
            details={"source": source, "actual_type": type(value).__name__},
        )
    return value


def _require_string(
    data: JSONObject,
    key: str,
    *,
    path: tuple[str, ...] | None = None,
    source: str,
) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise _load_error(
            code=f"load.{key}.type",
            message=f"Field '{key}' must be a string",
            path=path or (key,),
            details={"source": source, "actual_type": type(value).__name__},
        )
    return value


def _optional_string(
    data: JSONObject,
    key: str,
    *,
    path: tuple[str, ...] | None = None,
    source: str,
) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise _load_error(
        code=f"load.{key}.type",
        message=f"Field '{key}' must be a string",
        path=path or (key,),
        details={"source": source, "actual_type": type(value).__name__},
    )


def _require_string_item(value: JSONValue, *, path: tuple[str, ...], source: str) -> str:
    if isinstance(value, str):
        return value
    raise _load_error(
        code="load.checks.item_type",
        message="Check entries must be strings",
        path=path,
        details={"source": source, "actual_type": type(value).__name__},
    )


def _normalize_json_value(value: Any, *, source: str, path: tuple[str, ...]) -> JSONValue:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value

    if isinstance(value, list):
        return [_normalize_json_value(item, source=source, path=path + (str(index),)) for index, item in enumerate(value)]

    if isinstance(value, dict):
        normalized: JSONObject = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise _load_error(
                    code="load.json_key.type",
                    message="Object keys must be strings to remain JSON-shaped",
                    path=path,
                    details={"source": source, "actual_key_type": type(key).__name__},
                )
            normalized[key] = _normalize_json_value(item, source=source, path=path + (key,))
        return normalized

    raise _load_error(
        code="load.json_value.type",
        message="YAML value is not representable as canonical JSON-shaped data",
        path=path,
        details={"source": source, "actual_type": type(value).__name__},
    )


def _load_error(*, code: str, message: str, path: tuple[str, ...], details: JSONObject) -> LoadError:
    return LoadError(diagnostics=(Diagnostic(code=code, level="error", message=message, path=path, details=details),))
