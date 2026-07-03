"""Strict validation for workflow and profile declarations."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONObject, JSONValue
from ordo.model.runtime import RuntimeStatus

from .guard_expressions import GuardExpressionParseError, parse_guard_expression, validate_parsed_guard_expression
from .loading import LoadError, load_yaml_document

USES_PATTERN = re.compile(r"^[a-z0-9]+([._-][a-z0-9]+)*$")

WORKFLOW_ALLOWED_FIELDS = frozenset({"version", "workflow", "inputs", "states", "guards", "steps"})
CALL_ALLOWED_FIELDS = frozenset({"uses", "with"})
STEP_ALLOWED_FIELDS = frozenset({"name", "uses", "with"})
PROFILE_ALLOWED_FIELDS = frozenset({"name", "inputs", "checks", "overrides"})
OVERRIDE_ALLOWED_FIELDS = frozenset({"target", "with", "reason"})


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
    diagnostics.extend(_require_object_field(payload, "states", source=source, required=False))
    diagnostics.extend(_validate_guard_list(payload.get("guards"), source=source))
    diagnostics.extend(_validate_step_list(payload.get("steps"), source=source))

    return _report("workflow", diagnostics)


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


def _validate_guard_list(value: JSONValue | None, *, source: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not isinstance(value, list):
        diagnostics.append(_diagnostic("validation.workflow.guards.type", "Field 'guards' must be a list", ("guards",), source, actual_type=type(value).__name__))
        return diagnostics

    for index, item in enumerate(value):
        path = ("guards", str(index))
        if isinstance(item, str):
            if not item:
                diagnostics.append(_diagnostic("validation.workflow.guard_expr.empty", "Guard expression must not be empty", path, source))
                continue
            try:
                parsed = parse_guard_expression(item)
            except GuardExpressionParseError as exc:
                diagnostics.append(exc.to_diagnostic(path=path, source=source, expression=item))
                continue
            for validation_error in validate_parsed_guard_expression(parsed):
                diagnostics.append(validation_error.to_diagnostic(path=path, source=source, expression=item))
            continue
        diagnostics.extend(_validate_call(item, path=path, source=source))
    return diagnostics


def _validate_step_list(value: JSONValue | None, *, source: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not isinstance(value, list):
        diagnostics.append(_diagnostic("validation.workflow.steps.type", "Field 'steps' must be a list", ("steps",), source, actual_type=type(value).__name__))
        return diagnostics

    seen_names: dict[str, tuple[str, ...]] = {}
    for index, item in enumerate(value):
        path = ("steps", str(index))
        if not isinstance(item, dict):
            diagnostics.append(_diagnostic("validation.workflow.step.type", "Step entry must be an object", path, source, actual_type=type(item).__name__))
            continue

        diagnostics.extend(_validate_unknown_fields(item, STEP_ALLOWED_FIELDS, path=path, source=source))
        diagnostics.extend(_require_non_empty_string(item, "name", path=path + ("name",), source=source))
        diagnostics.extend(_validate_call(item, path=path, source=source, allowed_fields=STEP_ALLOWED_FIELDS))

        name = item.get("name")
        if isinstance(name, str) and name:
            if name in seen_names:
                diagnostics.append(_diagnostic("validation.workflow.step.duplicate_name", f"Duplicate step name '{name}'", path + ("name",), source, first_seen_path=list(seen_names[name])))
            else:
                seen_names[name] = path + ("name",)

    return diagnostics


def _validate_call(
    value: JSONValue,
    *,
    path: tuple[str, ...],
    source: str,
    allowed_fields: frozenset[str] = CALL_ALLOWED_FIELDS,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not isinstance(value, dict):
        diagnostics.append(_diagnostic("validation.workflow.call.type", "Operation entry must be an object", path, source, actual_type=type(value).__name__))
        return diagnostics

    if allowed_fields is CALL_ALLOWED_FIELDS:
        diagnostics.extend(_validate_unknown_fields(value, CALL_ALLOWED_FIELDS, path=path, source=source))

    diagnostics.extend(_require_non_empty_string(value, "uses", path=path + ("uses",), source=source, pattern=USES_PATTERN, pattern_message="Operation reference must match the stable connector operation pattern"))
    diagnostics.extend(_require_object_field(value, "with", path=path + ("with",), source=source, required=False))
    return diagnostics


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
