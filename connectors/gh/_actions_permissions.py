"""Shared gh repository Actions permissions helpers."""

from __future__ import annotations

import json

from connectors.gh._external import command_text, fail_github_command, text_mentions_not_found
from connectors.gh._repository import RepositoryIdentity
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, fail


def fetch_actions_permissions(
    ctx: OperationContext,
    *,
    identity: RepositoryIdentity,
    diagnostic_prefix: str,
    not_found_code: str,
    not_found_summary: str,
    failed_code: str,
    failed_summary: str,
) -> tuple[dict[str, object], dict[str, object]] | OperationOutcome:
    try:
        command = ctx.command(
            ["gh", "api", f"repos/{identity.owner}/{identity.repo}/actions/permissions"],
            failures={"os_error": failed_code},
        )
    except MappedOutcomeError as exc:
        outcome = exc.outcome
        text = command_text(outcome.raw)
        if outcome.status == "execution_error" and text_mentions_not_found(text, "repository not found", "not found"):
            return fail(
                code=not_found_code,
                summary=not_found_summary,
                diagnostics=(
                    Diagnostic(
                        code=f"{diagnostic_prefix}.repository_not_found",
                        level="error",
                        message=not_found_summary,
                        details={"reference": ctx.reference, "repository": identity.repository},
                    ),
                ),
                raw=outcome.raw,
            )
        return fail_github_command(
            ctx,
            code=failed_code,
            summary=failed_summary,
            raw=outcome.raw,
            diagnostic_code=f"{diagnostic_prefix}.command_failed",
            details={"repository": identity.repository},
            message=failed_summary,
        )

    try:
        payload = json.loads(command.stdout) if command.stdout else {}
    except json.JSONDecodeError as exc:
        return fail(
            code=failed_code,
            summary="GitHub Actions permissions output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_prefix}.invalid_json",
                    level="error",
                    message="GitHub Actions permissions output was not valid JSON",
                    details={"reference": ctx.reference, "repository": identity.repository, "error": str(exc)},
                ),
            ),
            raw=command.raw,
        )

    if not isinstance(payload, dict):
        return fail(
            code=failed_code,
            summary="GitHub Actions permissions output was not an object",
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_prefix}.invalid_shape",
                    level="error",
                    message="GitHub Actions permissions output was not an object",
                    details={"reference": ctx.reference, "repository": identity.repository},
                ),
            ),
            raw=command.raw,
        )

    enabled = payload.get("enabled")
    if not isinstance(enabled, bool):
        return fail(
            code=failed_code,
            summary="GitHub Actions permissions output did not include a boolean enabled flag",
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_prefix}.enabled_missing",
                    level="error",
                    message="GitHub Actions permissions output did not include a boolean enabled flag",
                    details={"reference": ctx.reference, "repository": identity.repository},
                ),
            ),
            raw=command.raw,
        )
    return payload, command.raw
