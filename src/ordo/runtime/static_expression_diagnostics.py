"""Static diagnostics for statically knowable runtime-value expression misuse."""

from __future__ import annotations

from dataclasses import dataclass

from ordo.model.diagnostic import Diagnostic
from ordo.model.json import JSONValue

from .local_expression_engine.core import BuiltinCallNode, LiteralNode, LocalExpressionParseError, ValueExpressionNode, parse_local_expression_tree


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
    diagnostics.extend(_apply_embedded_expression_rules(value, context=context))
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


def _apply_embedded_expression_rules(value: JSONValue, *, context: StaticExpressionRuleContext) -> list[Diagnostic]:
    if not isinstance(value, str) or not value.startswith("${") or not value.endswith("}"):
        return []
    try:
        parsed = parse_local_expression_tree(value[2:-1])
    except LocalExpressionParseError:
        return []
    return _diagnose_builtin_node(parsed.root, context=context)


def _diagnose_builtin_node(node: ValueExpressionNode, *, context: StaticExpressionRuleContext) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if isinstance(node, BuiltinCallNode) and node.name == "format":
        diagnostics.extend(_diagnose_format_builtin_call(node, context=context))
    for child in _iter_child_nodes(node):
        diagnostics.extend(_diagnose_builtin_node(child, context=context))
    return diagnostics


def _diagnose_format_builtin_call(node: BuiltinCallNode, *, context: StaticExpressionRuleContext) -> list[Diagnostic]:
    if not node.arguments or not isinstance(node.arguments[0], LiteralNode) or not isinstance(node.arguments[0].value, str):
        return []
    template = node.arguments[0].value
    arguments = len(node.arguments) - 1
    placeholders = template.count("{}")
    if placeholders == arguments:
        return []
    return [
        Diagnostic(
            code="validation.workflow.value_expr.format.placeholder_count",
            level="error",
            message="Value expression 'format' has a placeholder count that does not match the number of args",
            path=context.path,
            details={
                "source": context.source,
                "placeholders": placeholders,
                "arguments": arguments,
            },
        )
    ]


def _iter_child_nodes(node: ValueExpressionNode) -> list[ValueExpressionNode]:
    if isinstance(node, BuiltinCallNode):
        return list(node.arguments)
    if hasattr(node, "source") and hasattr(node, "filters"):
        children = [node.source]
        for filter_node in node.filters:
            children.extend(filter_node.arguments)
        return children
    if hasattr(node, "items"):
        return list(node.items)
    if hasattr(node, "operand"):
        return [node.operand]
    if hasattr(node, "left") and hasattr(node, "right"):
        return [node.left, node.right]
    if hasattr(node, "arguments"):
        return [argument.value if hasattr(argument, "value") else argument for argument in node.arguments]
    return []
