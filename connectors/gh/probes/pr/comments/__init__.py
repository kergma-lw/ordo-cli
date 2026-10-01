"""gh.pr.comments probe."""

from __future__ import annotations

from connectors.gh._pull_identity import PULL_IDENTITY_INPUTS, resolve_pull_identity
from connectors.gh.probes.pr._shared import fetch_json_list, fetch_pull_request, normalize_author, resolve_limit
from ordo.plugin_sdk import OperationContext, OperationOutcome, ok, probe
from ordo.model.human import declare_human


HUMAN = declare_human({'title': 'GitHub pr comments',
 'goal': 'connector_contexts.gh.repository already names the normal repository target and the workflow needs top-level '
         'PR discussion there by pull number.',
 'summary': 'Probe the regular conversation thread on one GitHub pull request as top-level discussion comments plus '
            'total count metadata. Prefer connector_contexts.gh.repository as the normal repository target and use an '
            'explicit repository argument only as a one-off override.',
 'sections': [{'heading': 'Use when',
               'items': ['connector_contexts.gh.repository already names the normal repository target and the workflow '
                         'needs top-level PR discussion there by pull number.',
                         'The workflow needs human conversation on the PR itself before summarizing discussion or '
                         'deciding whether follow-up is needed.']},
              {'heading': 'Do not use for',
               'items': ['Line-level review discussion attached to changed files; use connector.gh.pr.review_comments '
                         'for code-anchored comments.',
                         'Submitted review decisions such as APPROVED or CHANGES_REQUESTED; use '
                         'connector.gh.pr.reviews for review verdicts.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.gh.pr',
                               'summary': 'Parent PR snapshot probe that omits conversation thread details'},
                              {'handle': 'connector.gh.pr.review_comments',
                               'summary': 'Sibling probe for line-level code review comments instead of top-level '
                                          'conversation comments'},
                              {'handle': 'connector.gh.pr.reviews',
                               'summary': 'Sibling probe for submitted review decisions rather than free-form '
                                          'conversation comments'}]},
              {'heading': 'Examples', 'items': ['gh.pr.comments with inputs {"limit": 20, "pull_number": 42}']},
              {'heading': 'Inspect next',
               'items': ['connector.gh.pr.review_comments', 'connector.gh.pr.reviews', 'connector.gh.pr.timeline']}]})

def info():
    return probe(
        name="pr.comments",
        human=HUMAN,
        summary="Read regular conversation comments from a GitHub pull request.",
        inputs={**PULL_IDENTITY_INPUTS, "limit": "integer"},
        outputs={"pull_ref": "string", "total_count": "integer", "comments": ["object"]},
        failure_modes=("pull_not_found", "limit_invalid", "probe_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    identity = resolve_pull_identity(ctx, failure_code="probe_failed", diagnostic_prefix="probe.gh_pr_comments")
    if isinstance(identity, OperationOutcome):
        return identity
    limit = resolve_limit(
        ctx,
        pull_ref=identity.pull_ref,
        diagnostic_prefix="probe.gh_pr_comments",
        summary_subject="GitHub pull request comments",
    )
    if isinstance(limit, OperationOutcome):
        return limit
    fetched_pull = fetch_pull_request(ctx, identity=identity, diagnostic_prefix="probe.gh_pr_comments")
    if isinstance(fetched_pull, OperationOutcome):
        return fetched_pull
    pull_payload, pull_raw = fetched_pull
    fetched_comments = fetch_json_list(
        ctx,
        argv=["gh", "api", f"repos/{identity.owner}/{identity.repo}/issues/{identity.pull_number}/comments?per_page={limit}"],
        diagnostic_prefix="probe.gh_pr_comments",
        pull_ref=identity.pull_ref,
        failed_summary="GitHub pull request comments probe failed",
    )
    if isinstance(fetched_comments, OperationOutcome):
        return fetched_comments
    nodes, comments_raw = fetched_comments
    return ok(
        summary="GitHub pull request comments retrieved successfully",
        outputs={
            "pull_ref": identity.pull_ref,
            "total_count": pull_payload.get("comments", len(nodes)),
            "comments": [_normalize_comment(node) for node in nodes if isinstance(node, dict)],
        },
        raw={"pull": pull_raw, "comments": comments_raw},
    )


def _normalize_comment(node: dict[str, object]) -> dict[str, object]:
    return {
        "id": node.get("id"),
        "author": normalize_author(node.get("user")),
        "body": node.get("body"),
        "created_at": node.get("created_at"),
        "updated_at": node.get("updated_at"),
        "url": node.get("html_url"),
    }
