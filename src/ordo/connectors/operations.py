"""Compatibility dispatch surface for connector operations."""

from __future__ import annotations

from connectors._shared import not_implemented
from ordo.connectors.registry import get_public_action_handlers, get_public_probe_handlers


def execute_action(resolved_step, workflow):
    """Execute a supported action operation with structured results."""

    handler = get_public_action_handlers().get(resolved_step.reference)
    if handler is None:
        return not_implemented(resolved_step.reference, kind="action")
    return handler(resolved_step, workflow)


def evaluate_probe(resolved_guard, workflow):
    """Evaluate a supported probe operation with structured outputs."""

    handler = get_public_probe_handlers().get(resolved_guard.reference)
    if handler is None:
        return not_implemented(resolved_guard.reference, kind="probe")
    return handler(resolved_guard, workflow)
