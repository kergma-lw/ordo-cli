"""gh.repo.actions.permissions probe."""

from __future__ import annotations

from connectors.gh._actions_permissions import fetch_actions_permissions
from connectors.gh._repository import REPOSITORY_INPUTS, resolve_repository_identity
from ordo.plugin_sdk import OperationContext, OperationOutcome, ok, probe
from ordo.model.human import declare_human


HUMAN = declare_human({'title': 'GitHub repo actions permissions',
 'goal': 'connector_contexts.gh.repository already names the normal repository target and the workflow needs to decide '
         'whether GitHub Actions are currently enabled before repo.sync or another hosted mutation proceeds.',
 'summary': 'Probe GitHub Actions permissions for one repository, including whether Actions are enabled and the '
            'current hosted Actions policy shape. Prefer connector_contexts.gh.repository as the normal repository '
            'target and use an explicit repository argument only as a one-off override.',
 'sections': [{'heading': 'Use when',
               'items': ['connector_contexts.gh.repository already names the normal repository target and the workflow '
                         'needs to decide whether GitHub Actions are currently enabled before repo.sync or another '
                         'hosted mutation proceeds.',
                          'Later logic needs one typed snapshot of repository Actions policy instead of an opaque '
                          'shell response.']},
              {'heading': 'Do not use for',
               'items': ['Changing the repository Actions enabled state; use connector.gh.repo.actions.permissions.set '
                         'for that effectful update.',
                         'Inspecting local checkout automation state or workflow-run history; this surface is only the '
                         'repository Actions permissions snapshot.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.gh',
                               'summary': 'Parent GitHub connector family for repository, issue, pull-request, '
                                          'project, and repository-Actions operations'},
                              {'handle': 'connector.gh.repo',
                               'summary': 'Sibling repository identity probe for fork and default-branch facts'},
                              {'handle': 'connector.gh.repo.actions.permissions.set',
                               'summary': 'Sibling action for setting the repository Actions enabled state after '
                                          'reading the current policy'},
                              {'handle': 'connector.gh.repo.sync',
                               'summary': 'Sibling repository sync action that workflows may guard with the current '
                                          'Actions policy'}]},
              {'heading': 'Examples', 'items': ['gh.repo.actions.permissions with inputs {}']},
              {'heading': 'Inspect next',
               'items': ['connector.gh.repo.actions.permissions.set', 'connector.gh.repo', 'connector.gh.repo.sync']}]})

def info():
    return probe(
        name="repo.actions.permissions",
        human=HUMAN,
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
