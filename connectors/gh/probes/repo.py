"""gh.repo probe."""

from __future__ import annotations

from connectors.gh._repository import REPOSITORY_INPUTS, fetch_repository_payload, resolve_repository_identity
from ordo.plugin_sdk import OperationContext, OperationOutcome, ok, probe
from ordo.model.human import declare_human


HUMAN = declare_human({'title': 'GitHub repo',
 'goal': 'connector_contexts.gh.repository already names the normal repository target and the workflow needs one '
         'repository-level fact probe before deciding whether repo.sync can apply cleanly.',
 'summary': 'Probe one GitHub repository as a normalized identity and fork snapshot, including its default branch, '
            'fork status, parent repository, and archived flag. Prefer connector_contexts.gh.repository as the normal '
            'repository target and use an explicit repository argument only as a one-off override; review warns when '
            'it differs from the current gh context repository.',
 'sections': [{'heading': 'Use when',
               'items': ['connector_contexts.gh.repository already names the normal repository target and the workflow '
                         'needs one repository-level fact probe before deciding whether repo.sync can apply cleanly.',
                         "Later logic needs the repository's canonical name, default branch, or parent fork "
                         'relationship rather than issue-, PR-, or project-level facts.']},
              {'heading': 'Do not use for',
               'items': ["Syncing the repository's default branch; use connector.gh.repo.sync for that effectful "
                         'fork-sync operation.',
                         'Inspecting pull requests, issues, or GitHub Project membership; those remain separate '
                         'narrower GitHub surfaces.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.gh',
                               'summary': 'Parent GitHub connector family for repository, issue, pull-request, and '
                                          'project operations'},
                              {'handle': 'connector.gh.repo.sync',
                               'summary': 'Sibling action for syncing one fork repository default branch after this '
                                          'probe confirms fork facts'},
                              {'handle': 'connector.git.repo',
                               'summary': 'Sibling local Git repository probe for checkout-root and worktree facts '
                                          'rather than remote GitHub repository identity'},
                              {'handle': 'connector.gh.pr',
                               'summary': 'Sibling GitHub probe for pull-request facts once the workflow moves from '
                                          'repository-level to PR-level logic'}]},
              {'heading': 'Examples', 'items': ['gh.repo with inputs {}']},
              {'heading': 'Inspect next',
               'items': ['connector.gh.repo.sync', 'connector.git.repo', 'connector.gh.pr']}]})

def info():
    return probe(
        name="repo",
        human=HUMAN,
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
