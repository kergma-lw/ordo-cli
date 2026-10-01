"""gh.pr.reviews probe."""

from __future__ import annotations

from connectors.gh._pull_identity import PULL_IDENTITY_INPUTS, resolve_pull_identity
from connectors.gh.probes.pr._shared import fetch_graphql_payload, normalize_author, resolve_limit
from ordo.plugin_sdk import Diagnostic, OperationContext, OperationOutcome, fail, ok, probe
from ordo.model.human import declare_human

_QUERY = (
    "query($owner:String!,$repo:String!,$number:Int!,$limit:Int!){"
    "repository(owner:$owner,name:$repo){"
    "pullRequest(number:$number){"
    "reviews(first:$limit){totalCount nodes{id url body state submittedAt author{login} commit{oid}}}"
    "}}}"
)


HUMAN = declare_human({'title': 'GitHub pr reviews',
 'goal': 'connector_contexts.gh.repository already names the normal repository target and the workflow needs submitted '
         'review records there by pull number.',
 'summary': 'Probe submitted GitHub pull-request reviews as typed review records with verdict, author, timestamp, and '
            'optional reviewed commit id. Prefer connector_contexts.gh.repository as the normal repository target and '
            'use an explicit repository argument only as a one-off override.',
 'sections': [{'heading': 'Use when',
               'items': ['connector_contexts.gh.repository already names the normal repository target and the workflow '
                         'needs submitted review records there by pull number.',
                         'The workflow needs reviewer decisions such as APPROVED or CHANGES_REQUESTED without '
                         'reconstructing them from comments or timeline events.']},
              {'heading': 'Do not use for',
               'items': ['Free-form top-level discussion; use connector.gh.pr.comments when the workflow needs '
                         'ordinary PR conversation.',
                         'Per-line feedback details; use connector.gh.pr.review_comments for code-anchored remarks.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.gh.pr',
                               'summary': 'Parent PR snapshot that carries only aggregate review decision, not the '
                                          'individual submitted reviews'},
                              {'handle': 'connector.gh.pr.review_comments',
                               'summary': 'Sibling probe for detailed line-level review discussion'},
                              {'handle': 'connector.gh.pr.timeline',
                               'summary': 'Sibling probe for lifecycle events that may surround review activity'}]},
              {'heading': 'Examples', 'items': ['gh.pr.reviews with inputs {"limit": 20, "pull_number": 42}']},
              {'heading': 'Inspect next',
               'items': ['connector.gh.pr.review_comments', 'connector.gh.pr.timeline', 'connector.gh.pr']}]})

def info():
    return probe(
        name="pr.reviews",
        human=HUMAN,
        summary="Read submitted reviews from a GitHub pull request.",
        inputs={**PULL_IDENTITY_INPUTS, "limit": "integer"},
        outputs={"pull_ref": "string", "total_count": "integer", "reviews": ["object"]},
        failure_modes=("pull_not_found", "limit_invalid", "probe_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    identity = resolve_pull_identity(ctx, failure_code="probe_failed", diagnostic_prefix="probe.gh_pr_reviews")
    if isinstance(identity, OperationOutcome):
        return identity
    limit = resolve_limit(
        ctx,
        pull_ref=identity.pull_ref,
        diagnostic_prefix="probe.gh_pr_reviews",
        summary_subject="GitHub pull request reviews",
    )
    if isinstance(limit, OperationOutcome):
        return limit
    fetched = fetch_graphql_payload(
        ctx,
        query=_QUERY,
        owner=identity.owner,
        repo=identity.repo,
        pull_number=identity.pull_number,
        diagnostic_prefix="probe.gh_pr_reviews",
        failed_summary="GitHub pull request reviews probe failed",
        pull_ref=identity.pull_ref,
        limit=limit,
    )
    if isinstance(fetched, OperationOutcome):
        return fetched
    payload, raw = fetched
    repository_data = ((payload.get("data") or {}).get("repository")) if isinstance(payload.get("data"), dict) else None
    pull_data = ((repository_data or {}).get("pullRequest")) if isinstance(repository_data, dict) else None
    reviews_data = ((pull_data or {}).get("reviews")) if isinstance(pull_data, dict) else None
    if pull_data is None:
        return fail(
            code="pull_not_found",
            summary="GitHub pull request was not found",
            diagnostics=(
                Diagnostic(
                    code="probe.gh_pr_reviews.not_found",
                    level="error",
                    message="GitHub pull request was not found",
                    details={"reference": ctx.reference, "pull_ref": identity.pull_ref},
                ),
            ),
            raw=raw,
        )
    if not isinstance(reviews_data, dict):
        return fail(
            code="probe_failed",
            summary="GitHub pull request reviews output was not an object",
            diagnostics=(
                Diagnostic(
                    code="probe.gh_pr_reviews.invalid_shape",
                    level="error",
                    message="GitHub pull request reviews output was not an object",
                    details={"reference": ctx.reference, "pull_ref": identity.pull_ref},
                ),
            ),
            raw=raw,
        )
    nodes = reviews_data.get("nodes")
    total_count = reviews_data.get("totalCount")
    if not isinstance(nodes, list) or not isinstance(total_count, int):
        return fail(
            code="probe_failed",
            summary="GitHub pull request reviews output was missing required fields",
            diagnostics=(
                Diagnostic(
                    code="probe.gh_pr_reviews.missing_fields",
                    level="error",
                    message="GitHub pull request reviews output was missing required fields",
                    details={"reference": ctx.reference, "pull_ref": identity.pull_ref},
                ),
            ),
            raw=raw,
        )
    return ok(
        summary="GitHub pull request reviews retrieved successfully",
        outputs={
            "pull_ref": identity.pull_ref,
            "total_count": total_count,
            "reviews": [_normalize_review(node) for node in nodes if isinstance(node, dict)],
        },
        raw=raw,
    )


def _normalize_review(node: dict[str, object]) -> dict[str, object]:
    commit = node.get("commit")
    commit_id = commit.get("oid") if isinstance(commit, dict) else None
    return {
        "id": node.get("id"),
        "author": normalize_author(node.get("author")),
        "state": node.get("state"),
        "body": node.get("body"),
        "submitted_at": node.get("submittedAt"),
        "commit_id": commit_id,
        "url": node.get("url"),
    }
