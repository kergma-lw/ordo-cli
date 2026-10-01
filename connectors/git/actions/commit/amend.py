"""git.commit.amend action."""

from __future__ import annotations

from connectors.git.actions._shared import COMMIT_GRAPH_INVALIDATION, current_branch, head_commit, map_nonzero
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, fail_with_diagnostic, ok
from ordo.model.human import declare_human
from connectors.git.human import git_human


HUMAN = declare_human({'title': 'Git commit amend',
 'goal': 'A workflow intentionally needs amend semantics for the current HEAD commit rather than creating another '
         'follow-up commit.',
 'summary': 'Rewrite the current HEAD commit, optionally replacing its message, and return both the new commit id and '
            'the previous commit id.',
 'sections': [{'heading': 'Use when',
               'items': ['A workflow intentionally needs amend semantics for the current HEAD commit rather than '
                         'creating another follow-up commit.',
                         'Later logic needs both the rewritten commit id and the previous HEAD id to describe what '
                         'changed in history.']},
              {'heading': 'Result and boundary',
               'items': ['On success, the previous HEAD is replaced by a new revision, and both revisions are available '
                         'to later steps.',
                         'With no commit to amend, or when Git blocks the rewrite, the action does not report a replaced '
                         'HEAD.']},
              {'heading': 'Do not use for',
               'items': ['Creating an ordinary new commit from staged changes; use connector.git.commit.create when '
                         'history should advance without rewriting HEAD.',
                         'Undoing an older commit through a new compensating commit; use connector.git.commit.revert '
                         'for that history-preserving action.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.git.commit.create',
                               'summary': 'Sibling action for ordinary new commit creation instead of rewriting HEAD'},
                              {'handle': 'connector.git.commit.revert',
                               'summary': 'Sibling action for reverting one target commit instead of rewriting the '
                                          'current one'},
                              {'handle': 'connector.git.commits',
                                'summary': 'Read recent commit texts around the commit that was '
                                          'amended'},
                              {'handle': 'connector.git.branch',
                                'summary': 'Read current branch context before or after the amend'}]},
              {'heading': 'Examples',
               'items': ['git.commit.amend with inputs {"message": "Tighten commit message wording"}',
                         'git.commit.amend with inputs {"message": null}']},
              {'heading': 'Inspect next',
               'items': ['connector.git.commits', 'connector.git.commit.create', 'connector.git.branch']}]})

def info():
    return action(
        name="commit.amend",
        human=git_human(HUMAN, provide="`message`: optional; provide it to replace the current message, or omit it or use null to retain the message.", result="Returns commit, previous_commit, and branch. No existing commit or a blocked rewrite has no replaced-head result; rewritten history may require coordination before publication."),
        inputs={"message": "string | null"},
        effects=("rewrite the current HEAD commit",),
        outputs={"commit": "string", "previous_commit": "string", "branch": "string | null"},
        failure_modes=("message_invalid", "nothing_to_amend", "amend_blocked"),
        invalidates_observations=COMMIT_GRAPH_INVALIDATION,
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    message = _optional_message(ctx)
    if isinstance(message, OperationOutcome):
        return message

    branch = current_branch(ctx)
    if isinstance(branch, OperationOutcome):
        return branch

    previous_commit = head_commit(ctx)
    if isinstance(previous_commit, OperationOutcome):
        return fail_with_diagnostic(
            code="nothing_to_amend",
            summary="There is no HEAD commit to amend",
            diagnostic_code="action.git.nothing_to_amend",
            reference=ctx.reference,
            raw=previous_commit.raw,
        )

    argv = ["git", "commit", "--amend", "--no-edit"] if message is None else ["git", "commit", "--amend", "-m", message]

    try:
        command = ctx.command(
            argv,
            failures={"os_error": "amend_blocked", "nonzero": "amend_blocked"},
        )
    except MappedOutcomeError as exc:
        return map_nonzero(
            ctx,
            exc,
            cases=(("nothing to amend", "nothing_to_amend", "There is no commit state to amend", "action.git.nothing_to_amend"),),
            fallback_summary="Amending the current commit failed",
        )

    commit = head_commit(ctx)
    if isinstance(commit, OperationOutcome):
        return commit

    return ok(
        summary="Amended the current commit",
        outputs={"commit": commit, "previous_commit": previous_commit, "branch": branch},
        raw=command.raw,
    )


def _optional_message(ctx: OperationContext) -> str | None | OperationOutcome:
    try:
        value = ctx.input("message")
    except MappedOutcomeError as exc:
        if exc.outcome.status == "input_error":
            return None
        return exc.outcome

    if value is None:
        return None

    message = str(value)
    if not message.strip():
        return fail_with_diagnostic(
            code="message_invalid",
            summary="Commit message must not be empty",
            diagnostic_code="action.git.commit_message_invalid",
            reference=ctx.reference,
        )
    return message
