"""gh.pr probe."""

from __future__ import annotations

from connectors.gh._pull_identity import PULL_IDENTITY_INPUTS, resolve_pull_identity
from connectors.gh.probes.pr._shared import fetch_pull_request, normalize_author
from ordo.plugin_sdk import OperationContext, OperationOutcome, ok, probe


def info():
    return probe(
        name="pr",
        summary="Read normalized metadata from a GitHub pull request.",
        inputs=PULL_IDENTITY_INPUTS,
        outputs={
            "number": "integer",
            "repository": "string",
            "title": "string",
            "body": "string",
            "author": "object",
            "state": "string",
            "draft": "boolean",
            "url": "string",
            "created_at": "string",
            "updated_at": "string",
            "base_ref": "string",
            "head_ref": "string",
            "head_sha": "string",
            "mergeable": "boolean",
            "mergeable_state": "string",
            "review_decision": "string",
            "additions": "integer",
            "deletions": "integer",
            "changed_files": "integer",
            "commits_count": "integer",
        },
        failure_modes=("pull_not_found", "probe_failed"),
        handler=run,
        examples=(
            {
                "reference": "gh.pr",
                "inputs": {"pull_number": 42},
            },
        ),
    )


def run(ctx: OperationContext) -> OperationOutcome:
    identity = resolve_pull_identity(ctx, failure_code="probe_failed", diagnostic_prefix="probe.gh_pr")
    if isinstance(identity, OperationOutcome):
        return identity

    fetched = fetch_pull_request(ctx, identity=identity, diagnostic_prefix="probe.gh_pr")
    if isinstance(fetched, OperationOutcome):
        return fetched
    payload, raw = fetched
    return ok(summary="GitHub pull request retrieved successfully", outputs=_to_public_outputs(identity.repository, payload), raw=raw)


def _to_public_outputs(repository: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "number": payload.get("number"),
        "repository": repository,
        "title": payload.get("title"),
        "body": payload.get("body"),
        "author": normalize_author(payload.get("user")),
        "state": payload.get("state"),
        "draft": payload.get("draft"),
        "url": payload.get("html_url"),
        "created_at": payload.get("created_at"),
        "updated_at": payload.get("updated_at"),
        "base_ref": ((payload.get("base") or {}).get("ref")) if isinstance(payload.get("base"), dict) else None,
        "head_ref": ((payload.get("head") or {}).get("ref")) if isinstance(payload.get("head"), dict) else None,
        "head_sha": ((payload.get("head") or {}).get("sha")) if isinstance(payload.get("head"), dict) else None,
        "mergeable": payload.get("mergeable"),
        "mergeable_state": payload.get("mergeable_state"),
        "review_decision": payload.get("review_decision"),
        "additions": payload.get("additions"),
        "deletions": payload.get("deletions"),
        "changed_files": payload.get("changed_files"),
        "commits_count": payload.get("commits"),
    }
