"""gh.issue.create action."""

from __future__ import annotations

import re

from connectors.gh.actions._shared import ISSUE_INVENTORY_INVALIDATION
from connectors.gh._external import command_text, fail_github_command
from connectors.gh._repository import REPOSITORY_INPUTS, fetch_repository_payload, resolve_repository_identity
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, action, fail, ok
from ordo.model.human import declare_human

_ISSUE_URL_RE = re.compile(r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/issues/(?P<number>\d+)$")


HUMAN = declare_human({'title': 'Create GitHub issue',
 'goal': 'Open a new issue in the workflow\'s normal GitHub repository or in one deliberate repository override.',
 'summary': 'Create one new GitHub issue in one repository and return its canonical reference, number, title, and URL '
            'for later workflow steps. Prefer connector_contexts.gh.repository as the normal repository target and use '
            'an explicit repository argument only as a one-off override.',
 'sections': [{'heading': 'Use when',
               'items': ['The workflow must open a new issue and then reuse the returned issue number or URL in later '
                          'steps.']},
              {'heading': 'What to provide',
               'items': ['Provide a non-empty issue title. Optionally provide body text; omit it when the issue should '
                          'start without a body.',
                         'Use the workflow\'s GitHub repository context normally. Name a repository only for a deliberate '
                          'one-off target change.']},
              {'heading': 'Result and boundary',
               'items': ['Later steps can use the created issue\'s repository-qualified reference, number, title, or URL.',
                         'Creation can succeed before a later step fails and is not rolled back. It fails when the target '
                          'repository cannot be used, the title is blank, or GitHub blocks creation.']},
              {'heading': 'Do not use for',
               'items': ['Editing or commenting on an already existing issue; use the narrower body or comment actions '
                         'for that follow-up work.',
                         'Reading current issue metadata before deciding whether creation is necessary; use '
                         'connector.gh.issue or other probe surfaces first when the issue already exists.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.gh.issue',
                               'summary': 'Probe the created issue later when you need its full current snapshot'},
                              {'handle': 'connector.gh.issue.comment.add',
                               'summary': 'Add a follow-up comment to an existing issue instead of creating a new one'},
                              {'handle': 'connector.gh.issue.body.replace',
                               'summary': 'Rewrite the body of an existing issue instead of creating a fresh issue'}]},
              {'heading': 'Inspect next',
               'items': ['connector.gh.issue', 'connector.gh.issue.comment.add', 'connector.gh.issue.body.append']}]})

def info():
    return action(
        name="issue.create",
        human=HUMAN,
        inputs={**REPOSITORY_INPUTS, "title": "string", "body": "string | null"},
        effects=("create GitHub issue",),
        outputs={"issue_ref": "string", "repository": "string", "number": "integer", "url": "string", "title": "string"},
        failure_modes=("repository_not_found", "title_invalid", "create_blocked"),
        invalidates_observations=ISSUE_INVENTORY_INVALIDATION,
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    identity = resolve_repository_identity(ctx, failure_code="repository_not_found", diagnostic_prefix="action.gh_issue_create")
    if isinstance(identity, OperationOutcome):
        return identity
    repository = identity.repository
    title = str(ctx.input("title"))
    body = _optional_body(ctx)
    if isinstance(body, OperationOutcome):
        return body

    if not title.strip():
        return fail(
            code="title_invalid",
            summary="GitHub issue title must not be empty",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_create.title_invalid",
                    level="error",
                    message="GitHub issue title must not be empty",
                    details={"reference": ctx.reference, "repository": repository},
                ),
            ),
        )

    repository_lookup = _lookup_repository(ctx, identity=identity)
    if isinstance(repository_lookup, OperationOutcome):
        return repository_lookup

    command = ["gh", "issue", "create", "-R", repository, "--title", title]
    if body is not None:
        command.extend(["--body", body])

    try:
        create_command = ctx.command(command, failures={"os_error": "create_blocked", "nonzero": "create_blocked"})
    except MappedOutcomeError as exc:
        outcome = exc.outcome
        text = command_text(outcome.raw)
        if outcome.status == "create_blocked" and ("title can't be blank" in text or "title is required" in text):
            return fail(
                code="title_invalid",
                summary="GitHub issue title was rejected",
                diagnostics=(
                    Diagnostic(
                        code="action.gh_issue_create.title_invalid",
                        level="error",
                        message="GitHub issue title was rejected",
                        details={"reference": ctx.reference, "repository": repository, "title": title},
                    ),
                ),
                raw=outcome.raw,
            )
        return fail_github_command(
            ctx,
            code="create_blocked",
            summary="Creating GitHub issue failed",
            raw=outcome.raw,
            diagnostic_code="action.gh_issue_create.command_failed",
            details={"repository": repository, "title": title},
            message="Creating GitHub issue failed",
        )

    issue_data = _parse_issue_output(ctx, repository=repository, title=title, stdout=create_command.stdout, raw=create_command.raw)
    if isinstance(issue_data, OperationOutcome):
        return issue_data

    return ok(
        summary="Created GitHub issue",
        outputs={
            "issue_ref": issue_data["issue_ref"],
            "repository": repository,
            "number": issue_data["number"],
            "url": issue_data["url"],
            "title": issue_data["title"],
        },
        raw={"repository": repository_lookup.get("raw", {}), "create": create_command.raw},
    )


def _optional_body(ctx: OperationContext) -> str | None | OperationOutcome:
    try:
        value = ctx.input("body")
    except MappedOutcomeError as exc:
        if exc.outcome.status == "input_error":
            return None
        return exc.outcome
    if value is None:
        return None
    return str(value)


def _lookup_repository(ctx: OperationContext, *, identity) -> dict[str, object] | OperationOutcome:
    fetched = fetch_repository_payload(
        ctx,
        identity=identity,
        diagnostic_prefix="action.gh_issue_create",
        not_found_code="repository_not_found",
        not_found_summary="GitHub repository was not found",
        failed_code="create_blocked",
        failed_summary="Inspecting GitHub repository failed",
    )
    if isinstance(fetched, OperationOutcome):
        return fetched
    payload, raw = fetched
    return {"raw": raw, "repository": payload}


def _parse_issue_output(
    ctx: OperationContext, *, repository: str, title: str, stdout: str, raw: dict[str, object]
) -> dict[str, object] | OperationOutcome:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    url = next((line for line in reversed(lines) if line.startswith("https://github.com/")), "")
    match = _ISSUE_URL_RE.match(url)
    if match is None:
        return fail(
            code="create_blocked",
            summary="GitHub issue create output was missing the created issue URL",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_create.missing_fields",
                    level="error",
                    message="GitHub issue create output was missing the created issue URL",
                    details={"reference": ctx.reference, "repository": repository, "title": title},
                ),
            ),
            raw=raw,
        )

    created_repository = f"{match.group('owner')}/{match.group('repo')}"
    number = int(match.group("number"))
    if created_repository != repository:
        return fail(
            code="create_blocked",
            summary="GitHub issue create output repository did not match the request",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_create.invalid_shape",
                    level="error",
                    message="GitHub issue create output repository did not match the request",
                    details={
                        "reference": ctx.reference,
                        "repository": repository,
                        "created_repository": created_repository,
                        "title": title,
                    },
                ),
            ),
            raw=raw,
        )

    return {
        "issue_ref": f"{repository}#{number}",
        "number": number,
        "url": url,
        "title": title,
    }
