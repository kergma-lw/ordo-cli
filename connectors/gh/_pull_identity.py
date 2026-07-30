"""Shared gh pull request identity input helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, fail

PULL_IDENTITY_INPUTS = {"repository": "string", "pull_number": "integer"}

_MISSING = object()
_REPOSITORY_RE = re.compile(r"^(?P<owner>[^/]+)/(?P<repo>[^/]+)$")


@dataclass(frozen=True, slots=True)
class PullIdentity:
    repository: str
    pull_number: int
    pull_ref: str
    owner: str
    repo: str


def resolve_pull_identity(
    ctx: OperationContext,
    *,
    failure_code: str,
    diagnostic_prefix: str,
) -> PullIdentity | OperationOutcome:
    repository_value = _optional_input(ctx, "repository")
    if isinstance(repository_value, OperationOutcome):
        return repository_value
    pull_number_value = _optional_input(ctx, "pull_number")
    if isinstance(pull_number_value, OperationOutcome):
        return pull_number_value

    if repository_value is _MISSING:
        return _required_input_outcome(ctx, "repository")
    if pull_number_value is _MISSING:
        return _required_input_outcome(ctx, "pull_number")
    return _from_structured_inputs(
        ctx,
        repository_value=repository_value,
        pull_number_value=pull_number_value,
        failure_code=failure_code,
        diagnostic_prefix=diagnostic_prefix,
    )


def _from_structured_inputs(
    ctx: OperationContext,
    *,
    repository_value: object,
    pull_number_value: object,
    failure_code: str,
    diagnostic_prefix: str,
) -> PullIdentity | OperationOutcome:
    repository = str(repository_value)
    repository_match = _REPOSITORY_RE.match(repository)
    if repository_match is None:
        return fail(
            code=failure_code,
            summary="GitHub repository reference must use OWNER/REPO format",
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_prefix}.invalid_repository",
                    level="error",
                    message="GitHub repository reference must use OWNER/REPO format",
                    details={"reference": ctx.reference, "repository": repository},
                ),
            ),
        )

    pull_number = _coerce_pull_number(pull_number_value)
    if pull_number is None:
        return fail(
            code=failure_code,
            summary="GitHub pull request number must be a positive integer",
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_prefix}.invalid_pull_number",
                    level="error",
                    message="GitHub pull request number must be a positive integer",
                    details={"reference": ctx.reference, "repository": repository, "pull_number": pull_number_value},
                ),
            ),
        )

    owner = repository_match.group("owner")
    repo = repository_match.group("repo")
    return PullIdentity(
        repository=repository,
        pull_number=pull_number,
        pull_ref=f"{repository}#{pull_number}",
        owner=owner,
        repo=repo,
    )


def _optional_input(ctx: OperationContext, name: str) -> object | OperationOutcome:
    try:
        return ctx.input(name)
    except MappedOutcomeError as exc:
        if exc.outcome.status == "input_error":
            return _MISSING
        return exc.outcome


def _required_input_outcome(ctx: OperationContext, name: str) -> OperationOutcome:
    try:
        ctx.input(name)
    except MappedOutcomeError as exc:
        return exc.outcome
    return fail(
        code="input_error",
        summary=f"Required input '{name}' is missing",
        diagnostics=(
            Diagnostic(
                code="operation.input_missing",
                level="error",
                message=f"Required input '{name}' is missing",
                details={"reference": ctx.reference, "input": name},
            ),
        ),
    )


def _coerce_pull_number(value: object) -> int | None:
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
    return None
