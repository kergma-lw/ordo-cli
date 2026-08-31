"""gh.repo.sync action."""

from __future__ import annotations

from connectors.gh._external import fail_github_command
from connectors.gh._repository import REPOSITORY_INPUTS, fetch_repository_payload, resolve_repository_identity
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, action, fail, ok, preflight_observation


def info():
    return action(
        name="repo.sync",
        summary="Sync one GitHub fork repository default branch from its parent repository.",
        inputs=REPOSITORY_INPUTS,
        effects=("sync one fork repository default branch from its parent repository",),
        outputs={"repository": "string", "branch": "string", "upstream_repository": "string", "synced": "boolean"},
        failure_modes=("repository_not_found", "not_a_fork", "archived_repository", "default_branch_unavailable", "sync_blocked"),
        preflight_observations=(
            preflight_observation(
                probe="gh.repo",
                with_={},
                fields=("is_fork", "default_branch", "parent_repository", "archived"),
            ),
        ),
        handler=run,
        examples=(
            {"reference": "gh.repo.sync", "inputs": {}},
        ),
    )


def run(ctx: OperationContext) -> OperationOutcome:
    identity = resolve_repository_identity(ctx, failure_code="sync_blocked", diagnostic_prefix="action.gh_repo_sync")
    if isinstance(identity, OperationOutcome):
        return identity

    fetched = fetch_repository_payload(
        ctx,
        identity=identity,
        diagnostic_prefix="action.gh_repo_sync.repository_lookup",
        not_found_code="repository_not_found",
        not_found_summary="GitHub repository was not found",
        failed_code="sync_blocked",
        failed_summary="Inspecting GitHub repository failed",
    )
    if isinstance(fetched, OperationOutcome):
        return fetched
    payload, lookup_raw = fetched

    repository = str(payload.get("nameWithOwner") or identity.repository)
    if payload.get("isArchived") is True:
        return fail(
            code="archived_repository",
            summary="GitHub repository is archived and cannot be synced",
            diagnostics=(
                Diagnostic(
                    code="action.gh_repo_sync.archived_repository",
                    level="error",
                    message="GitHub repository is archived and cannot be synced",
                    details={"reference": ctx.reference, "repository": repository},
                ),
            ),
            raw={"repository": lookup_raw},
        )
    if payload.get("isFork") is not True:
        return fail(
            code="not_a_fork",
            summary="GitHub repository is not a fork and cannot be synced",
            diagnostics=(
                Diagnostic(
                    code="action.gh_repo_sync.not_a_fork",
                    level="error",
                    message="GitHub repository is not a fork and cannot be synced",
                    details={"reference": ctx.reference, "repository": repository},
                ),
            ),
            raw={"repository": lookup_raw},
        )

    default_branch_ref = payload.get("defaultBranchRef")
    branch = default_branch_ref.get("name") if isinstance(default_branch_ref, dict) else None
    if not isinstance(branch, str) or not branch.strip():
        return fail(
            code="default_branch_unavailable",
            summary="GitHub repository default branch was unavailable for sync",
            diagnostics=(
                Diagnostic(
                    code="action.gh_repo_sync.default_branch_unavailable",
                    level="error",
                    message="GitHub repository default branch was unavailable for sync",
                    details={"reference": ctx.reference, "repository": repository},
                ),
            ),
            raw={"repository": lookup_raw},
        )

    parent = payload.get("parent")
    upstream_repository = parent.get("nameWithOwner") if isinstance(parent, dict) else None
    if not isinstance(upstream_repository, str) or not upstream_repository.strip():
        return fail(
            code="sync_blocked",
            summary="GitHub fork parent repository was unavailable for sync",
            diagnostics=(
                Diagnostic(
                    code="action.gh_repo_sync.parent_repository_missing",
                    level="error",
                    message="GitHub fork parent repository was unavailable for sync",
                    details={"reference": ctx.reference, "repository": repository},
                ),
            ),
            raw={"repository": lookup_raw},
        )

    try:
        sync_command = ctx.command(
            ["gh", "repo", "sync", repository, "-b", branch],
            failures={"os_error": "sync_blocked", "nonzero": "sync_blocked"},
        )
    except MappedOutcomeError as exc:
        return fail_github_command(
            ctx,
            code="sync_blocked",
            summary="Syncing GitHub repository failed",
            raw=exc.outcome.raw,
            diagnostic_code="action.gh_repo_sync.command_failed",
            details={"repository": repository, "branch": branch, "upstream_repository": upstream_repository},
            message="Syncing GitHub repository failed",
        )

    return ok(
        summary="Synced GitHub repository default branch",
        outputs={"repository": repository, "branch": branch, "upstream_repository": upstream_repository, "synced": True},
        raw={"repository": lookup_raw, "sync": sync_command.raw},
    )
