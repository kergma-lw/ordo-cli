"""gh.issue.body.append action."""

from __future__ import annotations

import json

from connectors.gh._external import command_text, fail_github_command, text_mentions_not_found
from connectors.gh._issue_identity import ISSUE_IDENTITY_INPUTS, resolve_issue_identity
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, action, fail, ok
from ordo.model.human import declare_human
_DEFAULT_SEPARATOR = "\n\n"


HUMAN = declare_human({'title': 'GitHub issue body append',
 'goal': 'connector_contexts.gh.repository already names the normal repository target and the workflow should append '
         'one note to one issue body there.',
 'summary': 'Append one text fragment to the end of an existing GitHub issue body, optionally separated from the prior '
            'body by one explicit separator. Prefer connector_contexts.gh.repository as the normal repository target '
            'and use an explicit repository argument only as a one-off override.',
 'sections': [{'heading': 'Use when',
               'items': ['connector_contexts.gh.repository already names the normal repository target and the workflow '
                         'should append one note to one issue body there.',
                         'The workflow should preserve the current issue body and add one extra section, note, or '
                         'footer to it.']},
              {'heading': 'Do not use for',
               'items': ['Regenerating the whole canonical body from scratch; use connector.gh.issue.body.replace for '
                         'a full rewrite.',
                         'Adding conversational discussion that belongs in the comment thread instead of the issue '
                         'body; use connector.gh.issue.comment.add.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.gh.issue.body.replace',
                               'summary': 'Rewrite the full body instead of appending one trailing fragment'},
                              {'handle': 'connector.gh.issue.comment.add',
                               'summary': 'Write a discussion comment instead of mutating the issue body'},
                              {'handle': 'connector.gh.issue',
                               'summary': 'Probe the current body first when the append decision depends on existing '
                                          'issue metadata'}]},
              {'heading': 'Inspect next',
               'items': ['connector.gh.issue.body.replace', 'connector.gh.issue.comment.add', 'connector.gh.issue']}]})

def info():
    return action(
        name="issue.body.append",
        human=HUMAN,
        inputs={**ISSUE_IDENTITY_INPUTS, "text": "string", "separator": "string | null"},
        effects=("append text to GitHub issue body",),
        outputs={"issue_ref": "string", "url": "string", "body": "string", "changed": "boolean"},
        failure_modes=("issue_not_found", "text_invalid", "append_blocked"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    text = str(ctx.input("text"))
    separator = _optional_separator(ctx)
    if isinstance(separator, OperationOutcome):
        return separator

    identity = resolve_issue_identity(ctx, failure_code="append_blocked", diagnostic_prefix="action.gh_issue_body_append")
    if isinstance(identity, OperationOutcome):
        return identity

    issue_ref = identity.issue_ref
    owner = identity.owner
    repo = identity.repo
    number = identity.issue_number

    if not text.strip():
        return fail(
            code="text_invalid",
            summary="GitHub issue append text must not be empty",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_body_append.text_invalid",
                    level="error",
                    message="GitHub issue append text must not be empty",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
        )
    issue_data = _load_issue(ctx, issue_ref=issue_ref, owner=owner, repo=repo, number=number)
    if isinstance(issue_data, OperationOutcome):
        return issue_data

    current_body = issue_data["body"]
    issue_url = issue_data["url"]
    effective_separator = separator if separator is not None else _DEFAULT_SEPARATOR
    if current_body:
        new_body = current_body + effective_separator + text
    else:
        new_body = text

    try:
        command = ctx.command(
            ["gh", "issue", "edit", str(number), "-R", f"{owner}/{repo}", "--body", new_body],
            failures={"os_error": "append_blocked", "nonzero": "append_blocked"},
        )
    except MappedOutcomeError as exc:
        outcome = exc.outcome
        text_blob = command_text(outcome.raw)
        if outcome.status == "append_blocked" and ("body is too long" in text_blob or "invalid body" in text_blob):
            return fail(
                code="text_invalid",
                summary="GitHub issue append text was rejected",
                diagnostics=(
                    Diagnostic(
                        code="action.gh_issue_body_append.text_invalid",
                        level="error",
                        message="GitHub issue append text was rejected",
                        details={"reference": ctx.reference, "issue_ref": issue_ref},
                    ),
                ),
                raw=outcome.raw,
            )
        return fail_github_command(
            ctx,
            code="append_blocked",
            summary="Appending to GitHub issue body failed",
            raw=outcome.raw,
            diagnostic_code="action.gh_issue_body_append.command_failed",
            details={"issue_ref": issue_ref},
            message="Appending to GitHub issue body failed",
        )

    return ok(
        summary="Appended text to GitHub issue body",
        outputs={"issue_ref": issue_ref, "url": issue_url, "body": new_body, "changed": True},
        raw={"issue": issue_data.get("raw", {}), "edit": command.raw},
    )


def _optional_separator(ctx: OperationContext) -> str | None | OperationOutcome:
    try:
        value = ctx.input("separator")
    except MappedOutcomeError as exc:
        if exc.outcome.status == "input_error":
            return None
        return exc.outcome
    if value is None:
        return None
    return str(value)
def _load_issue(
    ctx: OperationContext, *, issue_ref: str, owner: str, repo: str, number: int
) -> dict[str, object] | OperationOutcome:
    try:
        command = ctx.command(
            ["gh", "issue", "view", str(number), "-R", f"{owner}/{repo}", "--json", "body,url"],
            failures={"os_error": "append_blocked", "nonzero": "append_blocked"},
        )
    except MappedOutcomeError as exc:
        outcome = exc.outcome
        text = command_text(outcome.raw)
        if outcome.status == "append_blocked" and text_mentions_not_found(text, "could not resolve to an issue", "issue not found"):
            return fail(
                code="issue_not_found",
                summary="GitHub issue was not found",
                diagnostics=(
                    Diagnostic(
                        code="action.gh_issue_body_append.issue_not_found",
                        level="error",
                        message="GitHub issue was not found",
                        details={"reference": ctx.reference, "issue_ref": issue_ref},
                    ),
                ),
                raw=outcome.raw,
            )
        return fail_github_command(
            ctx,
            code="append_blocked",
            summary="Inspecting GitHub issue failed",
            raw=outcome.raw,
            diagnostic_code="action.gh_issue_body_append.issue_lookup_failed",
            details={"issue_ref": issue_ref},
            message="Inspecting GitHub issue failed",
        )

    try:
        payload = json.loads(command.stdout) if command.stdout else {}
    except json.JSONDecodeError as exc:
        return fail(
            code="append_blocked",
            summary="GitHub issue output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_body_append.invalid_json",
                    level="error",
                    message="GitHub issue output was not valid JSON",
                    details={"reference": ctx.reference, "issue_ref": issue_ref, "error": str(exc)},
                ),
            ),
            raw=command.raw,
        )

    if not isinstance(payload, dict):
        return fail(
            code="append_blocked",
            summary="GitHub issue output was not an object",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_body_append.invalid_shape",
                    level="error",
                    message="GitHub issue output was not an object",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
            raw=command.raw,
        )

    body = payload.get("body")
    url = payload.get("url")
    if not isinstance(body, str) or not isinstance(url, str):
        return fail(
            code="append_blocked",
            summary="GitHub issue output was missing required fields",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_body_append.missing_fields",
                    level="error",
                    message="GitHub issue output was missing required fields",
                    details={"reference": ctx.reference, "issue_ref": issue_ref},
                ),
            ),
            raw=command.raw,
        )

    return {"body": body, "url": url, "raw": command.raw}
