"""Shared context policy for the canonical workflow-local expression engine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LocalExpressionRoot(StrEnum):
    """Documented root families visible to workflow-local expressions."""

    INPUTS = "inputs"
    ARGS = "args"
    STATE = "state"
    STEP = "step"


class LocalExpressionContext(StrEnum):
    """Semantic contexts in which local expressions may appear."""

    GUARD = "guard"
    STEP_CONDITION = "step_condition"
    EMBEDDED_VALUE = "embedded_value"
    INCLUDE_BINDING = "include_binding"


class LocalExpressionContextFamily(StrEnum):
    """Higher-level grouping of local-expression contexts."""

    CONDITION = "condition"
    VALUE = "value"


@dataclass(frozen=True, slots=True)
class LocalExpressionContextPolicy:
    """Semantic policy attached to one local-expression context."""

    context: LocalExpressionContext
    family: LocalExpressionContextFamily
    native_surface: bool
    launch_time_known_only: bool
    pure_only: bool
    hidden_control_forbidden: bool
    whole_tree_restrictions: bool
    allows_inputs: bool
    allows_args: bool
    allows_state: bool
    allows_step: bool

    def allows_root(self, root: LocalExpressionRoot) -> bool:
        return {
            LocalExpressionRoot.INPUTS: self.allows_inputs,
            LocalExpressionRoot.ARGS: self.allows_args,
            LocalExpressionRoot.STATE: self.allows_state,
            LocalExpressionRoot.STEP: self.allows_step,
        }[root]


LOCAL_EXPRESSION_CONTEXT_POLICIES: dict[LocalExpressionContext, LocalExpressionContextPolicy] = {
    LocalExpressionContext.GUARD: LocalExpressionContextPolicy(
        context=LocalExpressionContext.GUARD,
        family=LocalExpressionContextFamily.CONDITION,
        native_surface=True,
        launch_time_known_only=True,
        pure_only=True,
        hidden_control_forbidden=True,
        whole_tree_restrictions=True,
        allows_inputs=True,
        allows_args=False,
        allows_state=True,
        allows_step=False,
    ),
    LocalExpressionContext.STEP_CONDITION: LocalExpressionContextPolicy(
        context=LocalExpressionContext.STEP_CONDITION,
        family=LocalExpressionContextFamily.CONDITION,
        native_surface=True,
        launch_time_known_only=False,
        pure_only=True,
        hidden_control_forbidden=True,
        whole_tree_restrictions=True,
        allows_inputs=True,
        allows_args=True,
        allows_state=True,
        allows_step=True,
    ),
    LocalExpressionContext.EMBEDDED_VALUE: LocalExpressionContextPolicy(
        context=LocalExpressionContext.EMBEDDED_VALUE,
        family=LocalExpressionContextFamily.VALUE,
        native_surface=False,
        launch_time_known_only=False,
        pure_only=True,
        hidden_control_forbidden=True,
        whole_tree_restrictions=True,
        allows_inputs=True,
        allows_args=True,
        allows_state=True,
        allows_step=True,
    ),
    LocalExpressionContext.INCLUDE_BINDING: LocalExpressionContextPolicy(
        context=LocalExpressionContext.INCLUDE_BINDING,
        family=LocalExpressionContextFamily.VALUE,
        native_surface=False,
        launch_time_known_only=False,
        pure_only=True,
        hidden_control_forbidden=True,
        whole_tree_restrictions=True,
        allows_inputs=True,
        allows_args=False,
        allows_state=True,
        allows_step=True,
    ),
}


def get_local_expression_context_policy(context: LocalExpressionContext) -> LocalExpressionContextPolicy:
    """Return the semantic policy for one local-expression context."""

    return LOCAL_EXPRESSION_CONTEXT_POLICIES[context]
