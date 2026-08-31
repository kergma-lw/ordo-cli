"""Shared gh repository identity and lookup helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from connectors.gh._external import command_text, fail_github_command, text_mentions_not_found
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, fail

REPOSITORY_INPUTS: dict[str, str] = {"repository": "string"}

_REPOSITORY_RE = re.compile(r"^(?P<owner>[^/]+)/(?P<repo>[^/]+)$")


@dataclass(frozen=True, slots=True)
class RepositoryIdentity:
    repository: str
    owner: str
    repo: str
    diagnostics: tuple[Diagnostic, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class RepositoryTarget:
    repository: str
    diagnostics: tuple[Diagnostic, ...] = field(default_factory=tuple)


def resolve_repository_identity(
    ctx: OperationContext,
    *,
    failure_code: str,
    diagnostic_prefix: str,
) -> RepositoryIdentity | OperationOutcome:
    repository = resolve_repository_target(ctx, failure_code=failure_code, diagnostic_prefix=diagnostic_prefix)
    if isinstance(repository, OperationOutcome):
        return repository
    match = _REPOSITORY_RE.match(repository.repository)
    if match is None:
        return fail(
            code=failure_code,
            summary="GitHub repository reference must use OWNER/REPO format",
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_prefix}.invalid_repository",
                    level="error",
                    message="GitHub repository reference must use OWNER/REPO format",
                    details={"reference": ctx.reference, "repository": repository.repository},
                ),
            ),
        )
    return RepositoryIdentity(
        repository=repository.repository,
        owner=match.group("owner"),
        repo=match.group("repo"),
        diagnostics=repository.diagnostics,
    )


def normalize_repository_value(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    repository = value.strip()
    match = _REPOSITORY_RE.match(repository)
    if match is None:
        return None
    return repository


def split_repository(value: str) -> tuple[str, str] | None:
    match = _REPOSITORY_RE.match(value)
    if match is None:
        return None
    return match.group("owner"), match.group("repo")


def resolve_repository_target(
    ctx: OperationContext,
    *,
    failure_code: str,
    diagnostic_prefix: str,
) -> RepositoryTarget | OperationOutcome:
    explicit_value = ctx.optional_input("repository")
    explicit_repository = normalize_repository_value(explicit_value)
    if explicit_value is not None and explicit_repository is None:
        return fail(
            code=failure_code,
            summary="GitHub repository reference must use OWNER/REPO format",
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_prefix}.invalid_repository",
                    level="error",
                    message="GitHub repository reference must use OWNER/REPO format",
                    details={"reference": ctx.reference, "repository": explicit_value},
                ),
            ),
        )
    bootstrap_repository = normalize_repository_value(ctx.bootstrap().context.get("repository"))
    if explicit_repository and bootstrap_repository and explicit_repository != bootstrap_repository:
        return RepositoryTarget(
            repository=explicit_repository,
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_prefix}.repository_override",
                    level="warning",
                    message="Explicit GitHub repository overrides gh connector context repository",
                    details={
                        "reference": ctx.reference,
                        "repository": explicit_repository,
                        "context_repository": bootstrap_repository,
                    },
                ),
            ),
        )
    repository = explicit_repository or bootstrap_repository
    if repository is not None:
        return RepositoryTarget(repository=repository)
    return fail(
        code=failure_code,
        summary="GitHub repository target is required; set connector_contexts.gh.repository or pass repository explicitly",
        diagnostics=(
            Diagnostic(
                code=f"{diagnostic_prefix}.repository_missing",
                level="error",
                message="GitHub repository target is required; set connector_contexts.gh.repository or pass repository explicitly",
                details={"reference": ctx.reference},
            ),
        ),
    )


def fetch_repository_payload(
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
            [
                "gh",
                "api",
                "graphql",
                "-f",
                (
                    "query="
                    "query($owner:String!,$repo:String!){"
                    "repository(owner:$owner,name:$repo){"
                    "id nameWithOwner isFork isArchived "
                    "defaultBranchRef{name} "
                    "parent{nameWithOwner}"
                    "}}"
                ),
                "-f",
                f"owner={identity.owner}",
                "-f",
                f"repo={identity.repo}",
            ],
            failures={"os_error": failed_code},
        )
    except MappedOutcomeError as exc:
        outcome = exc.outcome
        text = command_text(outcome.raw)
        if outcome.status == "execution_error" and text_mentions_not_found(text, "could not resolve to a repository", "repository not found"):
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
            summary="GitHub repository output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_prefix}.invalid_json",
                    level="error",
                    message="GitHub repository output was not valid JSON",
                    details={"reference": ctx.reference, "repository": identity.repository, "error": str(exc)},
                ),
            ),
            raw=command.raw,
        )

    repository_data = ((payload.get("data") or {}).get("repository"))
    if repository_data is None:
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
            raw=command.raw,
        )
    if not isinstance(repository_data, dict):
        return fail(
            code=failed_code,
            summary="GitHub repository output was not an object",
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_prefix}.invalid_shape",
                    level="error",
                    message="GitHub repository output was not an object",
                    details={"reference": ctx.reference, "repository": identity.repository},
                ),
            ),
            raw=command.raw,
        )
    return repository_data, command.raw
