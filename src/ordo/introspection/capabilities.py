"""Published capability and expression metadata for machine-readable introspection."""

from __future__ import annotations

from ordo.model.json import JSONObject
from ordo.runtime.capabilities import EXPRESSION_ROOTS, EXPRESSION_SURFACES, NEGATIVE_RULES, RUNTIME_CAPABILITIES
from ordo.runtime.local_expression_engine.core import VALUE_EXPRESSION_BUILTINS, VALUE_EXPRESSION_FILTERS


def describe_capabilities() -> JSONObject:
    """Return the published capability and expression-surface metadata."""

    return {
        "capabilities": [capability.to_contract() for capability in RUNTIME_CAPABILITIES],
        "expression_roots": [root.to_contract() for root in EXPRESSION_ROOTS],
        "expression_surfaces": [surface.to_contract() for surface in EXPRESSION_SURFACES],
        "local_expression_filters": [spec.to_contract() for spec in VALUE_EXPRESSION_FILTERS.values()],
        "local_expression_builtins": [spec.to_contract() for spec in VALUE_EXPRESSION_BUILTINS.values()],
        "negative_rules": [rule.to_contract() for rule in NEGATIVE_RULES],
    }
