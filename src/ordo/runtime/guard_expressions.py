"""Compatibility wrapper for canonical guard-expression parsing and validation."""

from .local_expression_engine.core import *  # noqa: F401,F403

GuardExpressionNode = ConditionExpressionNode
ParsedGuardExpression = ParsedConditionExpression
GuardExpressionParseError = ConditionExpressionParseError
GuardExpressionValidationError = ConditionExpressionValidationError
