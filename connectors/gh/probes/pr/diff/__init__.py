"""gh.pr.diff probe."""

from __future__ import annotations

from connectors.gh._pull_identity import PULL_IDENTITY_INPUTS, resolve_pull_identity
from connectors.gh.probes.pr._shared import fetch_json_list, resolve_limit
from ordo.plugin_sdk import OperationContext, OperationOutcome, ok, probe


def info():
    return probe(
        name="pr.diff",
        summary="Read normalized file-level change summaries from a GitHub pull request.",
        inputs={**PULL_IDENTITY_INPUTS, "limit": "integer"},
        outputs={"pull_ref": "string", "total_files": "integer", "files": ["object"]},
        failure_modes=("pull_not_found", "limit_invalid", "probe_failed"),
        handler=run,
        examples=(
            {
                "reference": "gh.pr.diff",
                "inputs": {"repository": "owner/repo", "pull_number": 42},
            },
        ),
    )


def run(ctx: OperationContext) -> OperationOutcome:
    identity = resolve_pull_identity(ctx, failure_code="probe_failed", diagnostic_prefix="probe.gh_pr_diff")
    if isinstance(identity, OperationOutcome):
        return identity
    limit = resolve_limit(
        ctx,
        pull_ref=identity.pull_ref,
        diagnostic_prefix="probe.gh_pr_diff",
        summary_subject="GitHub pull request diff",
        default=100,
    )
    if isinstance(limit, OperationOutcome):
        return limit
    fetched = fetch_json_list(
        ctx,
        argv=["gh", "api", f"repos/{identity.owner}/{identity.repo}/pulls/{identity.pull_number}/files?per_page={limit}"],
        diagnostic_prefix="probe.gh_pr_diff",
        pull_ref=identity.pull_ref,
        failed_summary="GitHub pull request diff probe failed",
    )
    if isinstance(fetched, OperationOutcome):
        return fetched
    payload, raw = fetched
    files = [_normalize_file(item) for item in payload if isinstance(item, dict)]
    return ok(
        summary="GitHub pull request diff retrieved successfully",
        outputs={"pull_ref": identity.pull_ref, "total_files": len(files), "files": files},
        raw=raw,
    )


def _normalize_file(item: dict[str, object]) -> dict[str, object]:
    return {
        "path": item.get("filename"),
        "status": item.get("status"),
        "additions": item.get("additions"),
        "deletions": item.get("deletions"),
        "changes": item.get("changes"),
    }
