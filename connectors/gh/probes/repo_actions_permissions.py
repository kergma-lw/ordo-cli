"""gh.repo.actions.permissions probe."""

from __future__ import annotations

from connectors.gh._actions_permissions import fetch_actions_permissions
from connectors.gh._repository import REPOSITORY_INPUTS, resolve_repository_identity
from ordo.plugin_sdk import OperationContext, OperationOutcome, ok, probe


def info():
    return probe(
        name="repo.actions.permissions",
        summary="Read GitHub Actions permissions for one repository.",
        inputs=REPOSITORY_INPUTS,
        outputs={
            "repository": "string",
            "enabled": "boolean",
            "allowed_actions": "string | null",
            "sha_pinning_required": "boolean | null",
        },
        failure_modes=("repository_not_found", "probe_failed"),
        handler=run,
        examples=(
            {"reference": "gh.repo.actions.permissions", "inputs": {}},
        ),
    )


def run(ctx: OperationContext) -> OperationOutcome:
    identity = resolve_repository_identity(ctx, failure_code="probe_failed", diagnostic_prefix="probe.gh_repo_actions_permissions")
    if isinstance(identity, OperationOutcome):
        return identity
    fetched = fetch_actions_permissions(
        ctx,
        identity=identity,
        diagnostic_prefix="probe.gh_repo_actions_permissions",
        not_found_code="repository_not_found",
        not_found_summary="GitHub repository was not found",
        failed_code="probe_failed",
        failed_summary="GitHub Actions permissions probe failed",
    )
    if isinstance(fetched, OperationOutcome):
        return fetched
    payload, raw = fetched
    return ok(
        summary="GitHub Actions permissions retrieved successfully",
        outputs={
            "repository": identity.repository,
            "enabled": payload.get("enabled"),
            "allowed_actions": payload.get("allowed_actions") if isinstance(payload.get("allowed_actions"), str) else None,
            "sha_pinning_required": payload.get("sha_pinning_required") if isinstance(payload.get("sha_pinning_required"), bool) else None,
        },
        raw=raw,
    )
