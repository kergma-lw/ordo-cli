"""gh.repo probe."""

from __future__ import annotations

from connectors.gh._repository import REPOSITORY_INPUTS, fetch_repository_payload, resolve_repository_identity
from ordo.plugin_sdk import OperationContext, OperationOutcome, ok, probe


def info():
    return probe(
        name="repo",
        summary="Read normalized GitHub repository identity and fork facts.",
        inputs=REPOSITORY_INPUTS,
        outputs={
            "id": "string",
            "repository": "string",
            "default_branch": "string | null",
            "is_fork": "boolean",
            "parent_repository": "string | null",
            "archived": "boolean",
        },
        failure_modes=("repository_not_found", "probe_failed"),
        handler=run,
        examples=(
            {"reference": "gh.repo", "inputs": {}},
        ),
    )


def run(ctx: OperationContext) -> OperationOutcome:
    identity = resolve_repository_identity(ctx, failure_code="probe_failed", diagnostic_prefix="probe.gh_repo")
    if isinstance(identity, OperationOutcome):
        return identity

    fetched = fetch_repository_payload(
        ctx,
        identity=identity,
        diagnostic_prefix="probe.gh_repo",
        not_found_code="repository_not_found",
        not_found_summary="GitHub repository was not found",
        failed_code="probe_failed",
        failed_summary="GitHub repository probe failed",
    )
    if isinstance(fetched, OperationOutcome):
        return fetched
    payload, raw = fetched
    return ok(summary="GitHub repository retrieved successfully", outputs=_to_public_outputs(payload), raw=raw)


def _to_public_outputs(payload: dict[str, object]) -> dict[str, object]:
    default_branch = payload.get("defaultBranchRef")
    parent = payload.get("parent")
    return {
        "id": payload.get("id"),
        "repository": payload.get("nameWithOwner"),
        "default_branch": default_branch.get("name") if isinstance(default_branch, dict) else None,
        "is_fork": payload.get("isFork"),
        "parent_repository": parent.get("nameWithOwner") if isinstance(parent, dict) else None,
        "archived": payload.get("isArchived"),
    }
