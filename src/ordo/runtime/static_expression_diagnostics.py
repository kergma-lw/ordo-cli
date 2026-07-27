"""Static diagnostics for statically knowable runtime-value expression misuse."""

from __future__ import annotations

from dataclasses import dataclass

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONValue


@dataclass(frozen=True, slots=True)
class StaticExpressionRuleContext:
    path: tuple[str, ...]
    source: str


def collect_static_expression_diagnostics(
    value: JSONValue,
    *,
    path: tuple[str, ...],
    source: str,
) -> list[Diagnostic]:
    """Collect statically knowable diagnostics from runtime-value surfaces."""

    diagnostics: list[Diagnostic] = []
    context = StaticExpressionRuleContext(path=path, source=source)
    diagnostics.extend(_apply_format_rules(value, context=context))
    if isinstance(value, list):
        for index, item in enumerate(value):
            diagnostics.extend(
                collect_static_expression_diagnostics(
                    item,
                    path=path + (str(index),),
                    source=source,
                )
            )
        return diagnostics
    if isinstance(value, dict):
        for key, item in value.items():
            diagnostics.extend(
                collect_static_expression_diagnostics(
                    item,
                    path=path + (str(key),),
                    source=source,
                )
            )
    return diagnostics


def _apply_format_rules(value: JSONValue, *, context: StaticExpressionRuleContext) -> list[Diagnostic]:
    if not isinstance(value, dict) or "format" not in value or set(value.keys()) - {"format", "args"}:
        return []
    template = value.get("format")
    args = value.get("args", [])
    if not isinstance(template, str) or not isinstance(args, list):
        return []
    if any(_value_is_dynamic(item) for item in args):
        return []
    return [
        Diagnostic(
            code="validation.workflow.value_expr.format.placeholder_count",
            level="error",
            message="Field 'format' has a placeholder count that does not match the number of args",
            path=context.path,
            details={
                "source": context.source,
                "placeholders": template.count("{}"),
                "arguments": len(args),
            },
        )
    ] if template.count("{}") != len(args) else []


def _value_is_dynamic(value: JSONValue) -> bool:
    if isinstance(value, str):
        return value.startswith("${") and value.endswith("}")
    if isinstance(value, list):
        return any(_value_is_dynamic(item) for item in value)
    if isinstance(value, dict):
        return any(_value_is_dynamic(item) for item in value.values())
    return False
