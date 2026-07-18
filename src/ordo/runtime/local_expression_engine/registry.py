"""Canonical metadata registries for value-expression filters and builtins."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ordo.model.json import JSONObject, JSONValue

if False:  # pragma: no cover
    from .core import BuiltinCallNode, FilterApplicationNode, ParsedValueExpression
    from ordo.model.workflow import Workflow


FilterHandler = Callable[[JSONValue, "FilterApplicationNode", "ParsedValueExpression", "Workflow", dict], JSONValue]
BuiltinHandler = Callable[["BuiltinCallNode", "ParsedValueExpression", "Workflow"], JSONValue]


@dataclass(frozen=True, slots=True)
class ValueExpressionFilterSpec:
    """Canonical metadata for one published value-expression filter."""

    name: str
    input_type: str
    output_type: str
    handler: FilterHandler

    def to_contract(self) -> JSONObject:
        return {
            "name": self.name,
            "input_type": self.input_type,
            "output_type": self.output_type,
        }


@dataclass(frozen=True, slots=True)
class ValueExpressionBuiltinSpec:
    """Canonical metadata for one published value-expression builtin."""

    name: str
    handler: BuiltinHandler

    def to_contract(self) -> JSONObject:
        return {"name": self.name}


def build_filter_registry(*specs: ValueExpressionFilterSpec) -> dict[str, ValueExpressionFilterSpec]:
    return {spec.name: spec for spec in specs}


def build_builtin_registry(*specs: ValueExpressionBuiltinSpec) -> dict[str, ValueExpressionBuiltinSpec]:
    return {spec.name: spec for spec in specs}
