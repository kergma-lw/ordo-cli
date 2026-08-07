"""Structured workflow condition authoring support."""

from __future__ import annotations

from dataclasses import dataclass, field

from ordo.model.json import JSONObject, JSONValue


ConditionAuthoringValue = str | list[JSONValue] | dict[str, JSONValue]


@dataclass(frozen=True, slots=True)
class ConditionShapeError(Exception):
    """Structured condition shape error with machine-usable metadata."""

    code: str
    message: str
    path: tuple[str, ...]
    details: JSONObject


@dataclass(frozen=True, slots=True)
class ExpressionCondition:
    expression: str


@dataclass(frozen=True, slots=True)
class AllCondition:
    items: tuple[ConditionNode, ...]
    implicit: bool = False


@dataclass(frozen=True, slots=True)
class AnyCondition:
    items: tuple[ConditionNode, ...]


@dataclass(frozen=True, slots=True)
class NotCondition:
    item: ConditionNode


ConditionNode = ExpressionCondition | AllCondition | AnyCondition | NotCondition


@dataclass(frozen=True, slots=True)
class ConditionEvaluationNode:
    """Structured evaluation result for one condition node."""

    kind: str
    verdict: str
    path: tuple[str, ...]
    expression: str | None = None
    value: bool | None = None
    message: str | None = None
    code: str | None = None
    children: tuple[ConditionEvaluationNode, ...] = ()

    def to_contract(self) -> JSONObject:
        contract: JSONObject = {
            "kind": self.kind,
            "verdict": self.verdict,
            "path": list(self.path),
        }
        if self.expression is not None:
            contract["expression"] = self.expression
        if self.value is not None:
            contract["value"] = self.value
        if self.message is not None:
            contract["message"] = self.message
        if self.code is not None:
            contract["code"] = self.code
        if self.children:
            contract["children"] = [child.to_contract() for child in self.children]
        return contract


@dataclass(frozen=True, slots=True)
class ConditionEvaluationReport:
    """Structured evaluation report for one authored condition surface."""

    verdict: str
    root: ConditionEvaluationNode
    field_name: str = "if"
    failed: tuple[ConditionEvaluationNode, ...] = field(default_factory=tuple)
    unknown: tuple[ConditionEvaluationNode, ...] = field(default_factory=tuple)
    passed: tuple[ConditionEvaluationNode, ...] = field(default_factory=tuple)

    def to_contract(self) -> JSONObject:
        return {
            "field": self.field_name,
            "verdict": self.verdict,
            "root": self.root.to_contract(),
            "passed": [node.to_contract() for node in self.passed],
            "failed": [node.to_contract() for node in self.failed],
            "unknown": [node.to_contract() for node in self.unknown],
        }

_STRUCTURED_CONDITION_KEYS = frozenset({"all", "any", "not"})


def normalize_condition_authoring(
    value: JSONValue,
    *,
    path: tuple[str, ...] = (),
    field_name: str = "if",
) -> ConditionNode:
    """Normalize one authored condition surface into the shared internal tree."""

    code_prefix = f"validation.workflow.step.{field_name}"

    if isinstance(value, str):
        return ExpressionCondition(expression=value)
    if isinstance(value, list):
        return AllCondition(
            items=tuple(
                normalize_condition_authoring(item, path=path + (str(index),), field_name=field_name)
                for index, item in enumerate(value)
            ),
            implicit=True,
        )
    if isinstance(value, dict):
        keys = [key for key in value if isinstance(key, str)]
        if len(keys) != len(value):
            raise ConditionShapeError(
                code=f"{code_prefix}.shape",
                message=f"Structured step field '{field_name}' objects must use string keys",
                path=path,
                details={"actual_keys": list(value.keys())},
            )
        if len(keys) != 1:
            raise ConditionShapeError(
                code=f"{code_prefix}.shape",
                message=f"Structured step field '{field_name}' objects must define exactly one of 'all', 'any', or 'not'",
                path=path,
                details={"actual_keys": keys, "allowed_keys": sorted(_STRUCTURED_CONDITION_KEYS)},
            )
        operator = keys[0]
        if operator not in _STRUCTURED_CONDITION_KEYS:
            raise ConditionShapeError(
                code=f"{code_prefix}.shape",
                message=f"Unknown structured step field '{field_name}' operator '{operator}'",
                path=path + (operator,),
                details={"operator": operator, "allowed_keys": sorted(_STRUCTURED_CONDITION_KEYS)},
            )
        operand = value[operator]
        if operator in {"all", "any"}:
            if not isinstance(operand, list):
                raise ConditionShapeError(
                    code=f"{code_prefix}.{operator}.type",
                    message=f"Structured step field '{field_name}' operator '{operator}' must use a list value",
                    path=path + (operator,),
                    details={"operator": operator, "actual_type": type(operand).__name__},
                )
            items = tuple(normalize_condition_authoring(item, path=path + (operator, str(index)), field_name=field_name) for index, item in enumerate(operand))
            return AllCondition(items=items, implicit=False) if operator == "all" else AnyCondition(items=items)
        return NotCondition(item=normalize_condition_authoring(operand, path=path + (operator,), field_name=field_name))
    raise ConditionShapeError(
        code=f"{code_prefix}.type",
        message=f"Step field '{field_name}' must be a string-form or structured local expression",
        path=path,
        details={"actual_type": type(value).__name__},
    )


def iter_condition_expression_leaves(node: ConditionNode, *, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], str]]:
    """Return every string condition leaf together with its logical path."""

    if isinstance(node, ExpressionCondition):
        return [(path, node.expression)]
    if isinstance(node, NotCondition):
        return iter_condition_expression_leaves(node.item, path=path + ("not",))
    if isinstance(node, (AllCondition, AnyCondition)):
        operator = "all" if isinstance(node, AllCondition) else "any"
        leaves: list[tuple[tuple[str, ...], str]] = []
        for index, item in enumerate(node.items):
            if isinstance(node, AllCondition) and node.implicit:
                leaves.extend(iter_condition_expression_leaves(item, path=path + (str(index),)))
            else:
                leaves.extend(iter_condition_expression_leaves(item, path=path + (operator, str(index))))
        return leaves
    return []


def condition_authoring_has_structure(value: JSONValue | None) -> bool:
    return isinstance(value, (list, dict))
