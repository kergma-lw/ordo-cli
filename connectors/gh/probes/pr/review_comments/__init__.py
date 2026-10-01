"""gh.pr.review_comments probe."""

from __future__ import annotations

from connectors.gh._pull_identity import PULL_IDENTITY_INPUTS, resolve_pull_identity
from connectors.gh.probes.pr._shared import fetch_json_list, fetch_pull_request, normalize_author, resolve_limit
from ordo.plugin_sdk import OperationContext, OperationOutcome, ok, probe
from ordo.model.human import declare_human


HUMAN = declare_human({'title': 'GitHub pr review_comments',
 'goal': 'connector_contexts.gh.repository already names the normal repository target and the workflow needs '
         'file-anchored PR review comments there by pull number.',
 'summary': 'Probe line-level review comments on one GitHub pull request as typed code-anchored discussion records '
            'with path and line metadata. Prefer connector_contexts.gh.repository as the normal repository target and '
            'use an explicit repository argument only as a one-off override.',
 'sections': [{'heading': 'Use when',
               'items': ['connector_contexts.gh.repository already names the normal repository target and the workflow '
                         'needs file-anchored PR review comments there by pull number.',
                         'The workflow needs reviewer feedback tied to concrete files or lines rather than only '
                         'top-level PR conversation.']},
              {'heading': 'Do not use for',
               'items': ['Top-level conversation comments on the PR body; use connector.gh.pr.comments for that '
                         'broader discussion thread.',
                         'Submitted review verdicts without line detail; use connector.gh.pr.reviews for the '
                         'review-level decisions.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.gh.pr.diff',
                               'summary': 'Sibling probe for changed-file context that these line comments often '
                                          'reference'},
                              {'handle': 'connector.gh.pr.comments',
                               'summary': 'Sibling probe for top-level conversation comments rather than file-anchored '
                                          'review remarks'},
                              {'handle': 'connector.gh.pr.reviews',
                               'summary': 'Sibling probe for submitted review verdicts rather than individual line '
                                          'comments'}]},
              {'heading': 'Examples', 'items': ['gh.pr.review_comments with inputs {"limit": 20, "pull_number": 42}']},
              {'heading': 'Inspect next',
               'items': ['connector.gh.pr.diff', 'connector.gh.pr.reviews', 'connector.gh.pr.comments']}]})

def info():
    return probe(
        name="pr.review_comments",
        human=HUMAN,
        summary="Read line-level review comments from a GitHub pull request.",
        inputs={**PULL_IDENTITY_INPUTS, "limit": "integer"},
        outputs={"pull_ref": "string", "total_count": "integer", "comments": ["object"]},
        failure_modes=("pull_not_found", "limit_invalid", "probe_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    identity = resolve_pull_identity(ctx, failure_code="probe_failed", diagnostic_prefix="probe.gh_pr_review_comments")
    if isinstance(identity, OperationOutcome):
        return identity
    limit = resolve_limit(
        ctx,
        pull_ref=identity.pull_ref,
        diagnostic_prefix="probe.gh_pr_review_comments",
        summary_subject="GitHub pull request review comments",
    )
    if isinstance(limit, OperationOutcome):
        return limit
    fetched_pull = fetch_pull_request(ctx, identity=identity, diagnostic_prefix="probe.gh_pr_review_comments")
    if isinstance(fetched_pull, OperationOutcome):
        return fetched_pull
    pull_payload, pull_raw = fetched_pull
    fetched_comments = fetch_json_list(
        ctx,
        argv=["gh", "api", f"repos/{identity.owner}/{identity.repo}/pulls/{identity.pull_number}/comments?per_page={limit}"],
        diagnostic_prefix="probe.gh_pr_review_comments",
        pull_ref=identity.pull_ref,
        failed_summary="GitHub pull request review comments probe failed",
    )
    if isinstance(fetched_comments, OperationOutcome):
        return fetched_comments
    nodes, comments_raw = fetched_comments
    return ok(
        summary="GitHub pull request review comments retrieved successfully",
        outputs={
            "pull_ref": identity.pull_ref,
            "total_count": pull_payload.get("review_comments", len(nodes)),
            "comments": [_normalize_comment(node) for node in nodes if isinstance(node, dict)],
        },
        raw={"pull": pull_raw, "comments": comments_raw},
    )


def _normalize_comment(node: dict[str, object]) -> dict[str, object]:
    return {
        "id": node.get("id"),
        "author": normalize_author(node.get("user")),
        "body": node.get("body"),
        "path": node.get("path"),
        "commit_id": node.get("commit_id"),
        "original_commit_id": node.get("original_commit_id"),
        "line": node.get("line"),
        "original_line": node.get("original_line"),
        "side": node.get("side"),
        "in_reply_to_id": node.get("in_reply_to_id"),
        "created_at": node.get("created_at"),
        "updated_at": node.get("updated_at"),
        "url": node.get("html_url"),
    }
