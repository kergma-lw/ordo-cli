"""Configured remote validation for sync actions."""

from __future__ import annotations

from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, fail_with_diagnostic


def require_configured_remote(ctx: OperationContext, value: object, blocked_status: str) -> str | OperationOutcome:
    if not isinstance(value, str) or not value or value.startswith("-") or any(char.isspace() for char in value):
        return fail_with_diagnostic(
            code="remote_not_found",
            summary="Remote must be a nonempty configured name without whitespace or a leading '-'",
            diagnostic_code="action.git.invalid_remote",
            reference=ctx.reference,
        )

    try:
        command = ctx.command(["git", "remote"], failures={"os_error": blocked_status, "nonzero": blocked_status})
    except MappedOutcomeError:
        names = None
    else:
        names = command.stdout.splitlines() if isinstance(command.stdout, str) else None

    if names is None or len(names) != len(set(names)) or any(
        not name or name.startswith("-") or any(char.isspace() for char in name) for name in names
    ):
        # Inventory errors may contain configured URLs; do not forward raw output.
        return fail_with_diagnostic(
            code=blocked_status,
            summary="Could not read configured remote names",
            diagnostic_code="action.git.remote_inventory_failed",
            reference=ctx.reference,
        )

    if value not in names:
        return fail_with_diagnostic(
            code="remote_not_found",
            summary="Remote name is not configured in this repository",
            diagnostic_code="action.git.remote_not_found",
            reference=ctx.reference,
        )
    return value
