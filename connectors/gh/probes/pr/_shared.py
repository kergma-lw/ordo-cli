"""Shared gh.pr probe helpers."""

from __future__ import annotations

import json

from connectors.gh._external import command_text, fail_github_command, text_mentions_not_found
from connectors.gh._pull_identity import PullIdentity
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, fail


def resolve_limit(
    ctx: OperationContext,
    *,
    pull_ref: str,
    diagnostic_prefix: str,
    summary_subject: str,
    default: int = 20,
) -> int | OperationOutcome:
    try:
        raw = ctx.input("limit")
    except MappedOutcomeError as exc:
        if exc.outcome.status == "input_error":
            return default
        return exc.outcome
    limit = _coerce_positive_int(raw)
    if limit is None:
        return fail(
            code="limit_invalid",
            summary=f"{summary_subject} limit must be a positive integer",
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_prefix}.invalid_limit",
                    level="error",
                    message=f"{summary_subject} limit must be a positive integer",
                    details={"reference": ctx.reference, "pull_ref": pull_ref, "limit": raw},
                ),
            ),
        )
    return limit


def fetch_pull_request(
    ctx: OperationContext,
    *,
    identity: PullIdentity,
    diagnostic_prefix: str,
) -> tuple[dict[str, object], dict[str, object]] | OperationOutcome:
    try:
        command = ctx.command(
            [
                "gh",
                "api",
                f"repos/{identity.owner}/{identity.repo}/pulls/{identity.pull_number}",
            ],
            failures={"os_error": "probe_failed"},
        )
    except MappedOutcomeError as exc:
        return _map_command_error(
            ctx,
            outcome=exc.outcome,
            diagnostic_prefix=diagnostic_prefix,
            not_found_summary="GitHub pull request was not found",
            failed_summary="GitHub pull request probe failed",
            pull_ref=identity.pull_ref,
        )

    try:
        payload = json.loads(command.stdout) if command.stdout else {}
    except json.JSONDecodeError as exc:
        return fail(
            code="probe_failed",
            summary="GitHub pull request output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_prefix}.invalid_json",
                    level="error",
                    message="GitHub pull request output was not valid JSON",
                    details={"reference": ctx.reference, "pull_ref": identity.pull_ref, "error": str(exc)},
                ),
            ),
            raw=command.raw,
        )

    if not isinstance(payload, dict) or payload.get("number") is None:
        return fail(
            code="probe_failed",
            summary="GitHub pull request output was not an object",
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_prefix}.invalid_shape",
                    level="error",
                    message="GitHub pull request output was not an object",
                    details={"reference": ctx.reference, "pull_ref": identity.pull_ref},
                ),
            ),
            raw=command.raw,
        )
    return payload, command.raw


def fetch_json_list(
    ctx: OperationContext,
    *,
    argv: list[str],
    diagnostic_prefix: str,
    pull_ref: str,
    failed_summary: str,
) -> tuple[list[object], dict[str, object]] | OperationOutcome:
    try:
        command = ctx.command(argv, failures={"os_error": "probe_failed"})
    except MappedOutcomeError as exc:
        return _map_command_error(
            ctx,
            outcome=exc.outcome,
            diagnostic_prefix=diagnostic_prefix,
            not_found_summary="GitHub pull request was not found",
            failed_summary=failed_summary,
            pull_ref=pull_ref,
        )

    try:
        payload = json.loads(command.stdout) if command.stdout else []
    except json.JSONDecodeError as exc:
        return fail(
            code="probe_failed",
            summary=f"{failed_summary} output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_prefix}.invalid_json",
                    level="error",
                    message=f"{failed_summary} output was not valid JSON",
                    details={"reference": ctx.reference, "pull_ref": pull_ref, "error": str(exc)},
                ),
            ),
            raw=command.raw,
        )

    if not isinstance(payload, list):
        return fail(
            code="probe_failed",
            summary=f"{failed_summary} output was not a list",
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_prefix}.invalid_shape",
                    level="error",
                    message=f"{failed_summary} output was not a list",
                    details={"reference": ctx.reference, "pull_ref": pull_ref},
                ),
            ),
            raw=command.raw,
        )
    return payload, command.raw


def fetch_graphql_payload(
    ctx: OperationContext,
    *,
    query: str,
    owner: str,
    repo: str,
    pull_number: int,
    diagnostic_prefix: str,
    failed_summary: str,
    pull_ref: str,
    limit: int | None = None,
) -> tuple[dict[str, object], dict[str, object]] | OperationOutcome:
    argv = [
        "gh",
        "api",
        "graphql",
        "-f",
        f"query={query}",
        "-f",
        f"owner={owner}",
        "-f",
        f"repo={repo}",
        "-F",
        f"number={pull_number}",
    ]
    if limit is not None:
        argv.extend(["-F", f"limit={limit}"])
    try:
        command = ctx.command(argv, failures={"os_error": "probe_failed"})
    except MappedOutcomeError as exc:
        return _map_command_error(
            ctx,
            outcome=exc.outcome,
            diagnostic_prefix=diagnostic_prefix,
            not_found_summary="GitHub pull request was not found",
            failed_summary=failed_summary,
            pull_ref=pull_ref,
        )

    try:
        payload = json.loads(command.stdout) if command.stdout else {}
    except json.JSONDecodeError as exc:
        return fail(
            code="probe_failed",
            summary=f"{failed_summary} output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_prefix}.invalid_json",
                    level="error",
                    message=f"{failed_summary} output was not valid JSON",
                    details={"reference": ctx.reference, "pull_ref": pull_ref, "error": str(exc)},
                ),
            ),
            raw=command.raw,
        )
    if not isinstance(payload, dict):
        return fail(
            code="probe_failed",
            summary=f"{failed_summary} output was not an object",
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_prefix}.invalid_shape",
                    level="error",
                    message=f"{failed_summary} output was not an object",
                    details={"reference": ctx.reference, "pull_ref": pull_ref},
                ),
            ),
            raw=command.raw,
        )
    return payload, command.raw


def normalize_author(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    login = value.get("login")
    if login is None:
        return None
    return {"login": login}


def _map_command_error(
    ctx: OperationContext,
    *,
    outcome,
    diagnostic_prefix: str,
    not_found_summary: str,
    failed_summary: str,
    pull_ref: str,
) -> OperationOutcome:
    text = command_text(outcome.raw)
    if outcome.status == "execution_error" and text_mentions_not_found(text, "could not resolve to a pull request"):
        return fail(
            code="pull_not_found",
            summary=not_found_summary,
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_prefix}.not_found",
                    level="error",
                    message=not_found_summary,
                    details={"reference": ctx.reference, "pull_ref": pull_ref},
                ),
            ),
            raw=outcome.raw,
        )
    if outcome.status == "execution_error":
        return fail_github_command(
            ctx,
            code="probe_failed",
            summary=failed_summary,
            raw=outcome.raw,
            diagnostic_code=f"{diagnostic_prefix}.command_failed",
            details={"pull_ref": pull_ref},
            message=failed_summary,
        )
    return outcome


def _coerce_positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            number = int(stripped)
            return number if number > 0 else None
    return None
