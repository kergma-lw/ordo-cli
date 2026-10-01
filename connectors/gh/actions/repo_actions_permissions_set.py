"""gh.repo.actions.permissions.set action."""

from __future__ import annotations

from connectors.gh._actions_permissions import fetch_actions_permissions
from connectors.gh._external import fail_github_command
from connectors.gh._repository import REPOSITORY_INPUTS, resolve_repository_identity
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, action, fail, ok, preflight_observation
from ordo.model.human import declare_human


HUMAN = declare_human({'title': 'GitHub repo actions permissions set',
 'goal': 'connector_contexts.gh.repository already names the normal repository target and the workflow needs to '
         'disable or re-enable hosted GitHub Actions there as an explicit step before later repo-level work.',
 'summary': 'Set the GitHub Actions enabled state for one repository and report the resulting enabled flag together '
            'with whether the repository policy changed. Prefer connector_contexts.gh.repository as the normal '
            'repository target and use an explicit repository argument only as a one-off override.',
 'sections': [{'heading': 'Use when',
               'items': ['connector_contexts.gh.repository already names the normal repository target and the workflow '
                         'needs to disable or re-enable hosted GitHub Actions there as an explicit step before later '
                         'repo-level work.',
                         'The authored intent is one narrow repository Actions policy mutation, not a hidden '
                         'multi-step sync helper.']},
              {'heading': 'Do not use for',
               'items': ['Reading the current repository Actions policy without changing it; use '
                         'connector.gh.repo.actions.permissions for that probe.',
                         'Composing a temporary disable-sync-restore sequence inside one action; keep those steps '
                         'explicit in the workflow instead of hiding orchestration inside this leaf action.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.gh.repo.actions.permissions',
                               'summary': 'Sibling probe for the current repository Actions policy before or after '
                                          'mutation'},
                              {'handle': 'connector.gh.repo.sync',
                               'summary': 'Sibling repository sync action that can appear between explicit disable and '
                                          'restore steps'},
                              {'handle': 'connector.gh.repo',
                               'summary': 'Sibling repository identity probe for repo-level targeting facts'},
                              {'handle': 'connector.git.sync.fetch',
                               'summary': 'Local Git sync action when the real target is a local clone rather than '
                                          'hosted Actions policy'}]},
              {'heading': 'Examples', 'items': ['gh.repo.actions.permissions.set with inputs {"enabled": false}']},
              {'heading': 'Inspect next',
               'items': ['connector.gh.repo.actions.permissions', 'connector.gh.repo.sync', 'connector.gh.repo']}]})

def info():
    return action(
        name="repo.actions.permissions.set",
        human=HUMAN,
        summary="Set the GitHub Actions enabled state for one repository.",
        inputs={**REPOSITORY_INPUTS, "enabled": "boolean"},
        effects=("set the GitHub Actions enabled state for one repository",),
        outputs={"repository": "string", "enabled": "boolean", "changed": "boolean"},
        failure_modes=("repository_not_found", "set_blocked"),
        preflight_observations=(
            preflight_observation(
                probe="gh.repo.actions.permissions",
                with_={},
                fields=("enabled",),
            ),
        ),
        handler=run,
        examples=(
            {"reference": "gh.repo.actions.permissions.set", "inputs": {"enabled": False}},
        ),
    )


def run(ctx: OperationContext) -> OperationOutcome:
    identity = resolve_repository_identity(ctx, failure_code="set_blocked", diagnostic_prefix="action.gh_repo_actions_permissions_set")
    if isinstance(identity, OperationOutcome):
        return identity
    desired_enabled = ctx.input("enabled")
    if not isinstance(desired_enabled, bool):
        return fail(
            code="set_blocked",
            summary="GitHub Actions enabled state must be a boolean",
            diagnostics=(
                Diagnostic(
                    code="action.gh_repo_actions_permissions_set.invalid_enabled",
                    level="error",
                    message="GitHub Actions enabled state must be a boolean",
                    details={"reference": ctx.reference, "repository": identity.repository, "enabled": desired_enabled},
                ),
            ),
        )

    fetched = fetch_actions_permissions(
        ctx,
        identity=identity,
        diagnostic_prefix="action.gh_repo_actions_permissions_set",
        not_found_code="repository_not_found",
        not_found_summary="GitHub repository was not found",
        failed_code="set_blocked",
        failed_summary="Inspecting GitHub Actions permissions failed",
    )
    if isinstance(fetched, OperationOutcome):
        return fetched
    current_payload, current_raw = fetched
    current_enabled = current_payload.get("enabled")
    if current_enabled is desired_enabled:
        return ok(
            summary="GitHub Actions enabled state already matched the requested value",
            outputs={"repository": identity.repository, "enabled": desired_enabled, "changed": False},
            raw={"before": current_raw},
        )

    try:
        command = ctx.command(
            [
                "gh",
                "api",
                f"repos/{identity.owner}/{identity.repo}/actions/permissions",
                "--method",
                "PUT",
                "-F",
                f"enabled={'true' if desired_enabled else 'false'}",
            ],
            failures={"os_error": "set_blocked", "nonzero": "set_blocked"},
        )
    except MappedOutcomeError as exc:
        return fail_github_command(
            ctx,
            code="set_blocked",
            summary="Updating GitHub Actions permissions failed",
            raw=exc.outcome.raw,
            diagnostic_code="action.gh_repo_actions_permissions_set.command_failed",
            details={"repository": identity.repository, "enabled": desired_enabled},
            message="Updating GitHub Actions permissions failed",
        )

    verified = fetch_actions_permissions(
        ctx,
        identity=identity,
        diagnostic_prefix="action.gh_repo_actions_permissions_set.verify",
        not_found_code="repository_not_found",
        not_found_summary="GitHub repository was not found",
        failed_code="set_blocked",
        failed_summary="Verifying GitHub Actions permissions failed",
    )
    if isinstance(verified, OperationOutcome):
        return verified
    verified_payload, verified_raw = verified
    enabled = verified_payload.get("enabled")
    if enabled is not desired_enabled:
        return fail(
            code="set_blocked",
            summary="GitHub Actions enabled state did not match the requested value after update",
            diagnostics=(
                Diagnostic(
                    code="action.gh_repo_actions_permissions_set.postcondition_failed",
                    level="error",
                    message="GitHub Actions enabled state did not match the requested value after update",
                    details={"reference": ctx.reference, "repository": identity.repository, "enabled": desired_enabled},
                ),
            ),
            raw={"before": current_raw, "update": command.raw, "after": verified_raw},
        )

    return ok(
        summary="Updated GitHub Actions enabled state",
        outputs={"repository": identity.repository, "enabled": enabled, "changed": True},
        raw={"before": current_raw, "update": command.raw, "after": verified_raw},
    )
