"""git.branch.create action."""

from __future__ import annotations

from connectors.git.actions._shared import BRANCH_INVENTORY_INVALIDATION, head_commit, require_branch_name, require_commit, require_local_branch
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, fail_with_diagnostic, ok
from ordo.model.human import declare_human
from connectors.git.human import git_human


HUMAN = declare_human({'title': 'Git branch create',
 'goal': 'A workflow needs to create a local working branch before switching to it or using it in later Git '
         'operations.',
 'summary': 'Create one new local Git branch, optionally from an explicit start point, without switching the current '
            'checkout automatically.',
 'sections': [{'heading': 'Use when',
               'items': ['A workflow needs to create a local working branch before switching to it or using it in '
                          'later Git operations.',
                           'Use this to create a branch, not for a broader repository clone, fetch, or '
                          'checkout workflow.']},
              {'heading': 'Result and boundary',
               'items': ['On success, the named local branch exists at the selected starting revision while the current '
                         'checkout stays where it was.',
                         'An existing branch, missing starting revision, or other Git block does not produce a new '
                         'branch result.']},
              {'heading': 'Do not use for',
               'items': ['Switching the current checkout to the new or existing branch; use '
                         'connector.git.branch.switch for that mutation.',
                         'Inspecting whether a branch already exists; use connector.git.branches or connector.git.ref '
                         'when the workflow only needs a read path.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.git.branch',
                                'summary': 'Read current-branch context before or after '
                                          'branch creation'},
                              {'handle': 'connector.git.branch.switch',
                               'summary': 'Typical follow-up action for moving the current checkout onto the created '
                                          'branch'},
                              {'handle': 'connector.git.branches',
                                'summary': 'List branches before or after creation'},
                              {'handle': 'connector.git.ref',
                                'summary': 'Check one explicit ref when a full branch '
                                          'inventory is unnecessary'}]},
              {'heading': 'Examples',
               'items': ['git.branch.create with inputs {"branch": "feature/demo", "start_point": "HEAD"}']},
              {'heading': 'Inspect next',
               'items': ['connector.git.branch.switch', 'connector.git.branches', 'connector.git.branch']}]})

def info():
    return action(
        name="branch.create",
        human=git_human(HUMAN, provide="`branch`: required. `start_point`: optional; provide a revision or null, or omit it to begin at the current head.", result="Returns branch and start_point. Existing names, missing start points, or blocks do not create a branch, and the current checkout remains unchanged on success."),
        inputs={"branch": "string", "start_point": "string | null"},
        effects=("create a new local branch",),
        outputs={"branch": "string", "start_point": "string"},
        failure_modes=("invalid_branch", "branch_exists", "start_point_not_found", "create_blocked"),
        invalidates_observations=BRANCH_INVENTORY_INVALIDATION,
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    branch = str(ctx.input("branch"))
    start_point_input = _optional_start_point(ctx)
    if isinstance(start_point_input, OperationOutcome):
        return start_point_input

    invalid_branch = require_branch_name(ctx, branch)
    if invalid_branch is not None:
        return invalid_branch

    existing_branch = require_local_branch(ctx, branch)
    if existing_branch is None:
        return fail_with_diagnostic(
            code="branch_exists",
            summary=f"Local branch '{branch}' already exists",
            diagnostic_code="action.git.branch_exists",
            reference=ctx.reference,
        )

    if start_point_input is None:
        start_point = head_commit(ctx)
        if isinstance(start_point, OperationOutcome):
            return start_point
        command_argv = ["git", "branch", branch]
    else:
        start_point = require_commit(
            ctx,
            start_point_input,
            code="start_point_not_found",
            summary=f"Start point '{start_point_input}' was not found",
            diagnostic_code="action.git.start_point_not_found",
        )
        if isinstance(start_point, OperationOutcome):
            return start_point
        command_argv = ["git", "branch", branch, start_point_input]

    try:
        command = ctx.command(command_argv, failures={"os_error": "create_blocked", "nonzero": "create_blocked"})
    except MappedOutcomeError as exc:
        return fail_with_diagnostic(
            code="create_blocked",
            summary=f"Creating branch '{branch}' failed",
            diagnostic_code="action.git.branch_create_blocked",
            reference=ctx.reference,
            raw=exc.outcome.raw,
        )

    return ok(
        summary=f"Created branch '{branch}'",
        outputs={"branch": branch, "start_point": start_point},
        raw=command.raw,
    )


def _optional_start_point(ctx: OperationContext) -> str | None | OperationOutcome:
    try:
        value = ctx.input("start_point")
    except MappedOutcomeError as exc:
        if exc.outcome.status == "input_error":
            return None
        return exc.outcome
    if value is None:
        return None
    return str(value)
