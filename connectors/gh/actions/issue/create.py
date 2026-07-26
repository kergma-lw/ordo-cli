"""gh.issue.create action."""

from __future__ import annotations

import json
import re

from connectors.gh.actions._shared import ISSUE_INVENTORY_INVALIDATION
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, action, fail, ok

_REPOSITORY_RE = re.compile(r"^(?P<owner>[^/]+)/(?P<repo>[^/]+)$")
_ISSUE_URL_RE = re.compile(r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/issues/(?P<number>\d+)$")


def info():
    return action(
        name="issue.create",
        inputs={"repository": "string", "title": "string", "body": "string | null"},
        effects=("create GitHub issue",),
        outputs={"issue_ref": "string", "repository": "string", "number": "integer", "url": "string", "title": "string"},
        failure_modes=("repository_not_found", "title_invalid", "create_blocked"),
        invalidates_observations=ISSUE_INVENTORY_INVALIDATION,
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    repository = str(ctx.input("repository"))
    title = str(ctx.input("title"))
    body = _optional_body(ctx)
    if isinstance(body, OperationOutcome):
        return body

    parsed = _parse_repository(repository)
    if parsed is None:
        return fail(
            code="repository_not_found",
            summary="GitHub repository reference must use OWNER/REPO format",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_create.invalid_repository",
                    level="error",
                    message="GitHub repository reference must use OWNER/REPO format",
                    details={"reference": ctx.reference, "repository": repository},
                ),
            ),
        )

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

    owner, repo = parsed
    repository_lookup = _lookup_repository(ctx, repository=repository, owner=owner, repo=repo)
    if isinstance(repository_lookup, OperationOutcome):
        return repository_lookup

    command = ["gh", "issue", "create", "-R", repository, "--title", title]
    if body is not None:
        command.extend(["--body", body])

    try:
        create_command = ctx.command(command, failures={"os_error": "create_blocked", "nonzero": "create_blocked"})
    except MappedOutcomeError as exc:
        outcome = exc.outcome
        text = f"{outcome.raw.get('stderr', '')}\n{outcome.raw.get('stdout', '')}".lower()
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
        return fail(
            code="create_blocked",
            summary="Creating GitHub issue failed",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_create.command_failed",
                    level="error",
                    message="Creating GitHub issue failed",
                    details={"reference": ctx.reference, "repository": repository, "title": title},
                ),
            ),
            raw=outcome.raw,
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


def _parse_repository(value: str) -> tuple[str, str] | None:
    match = _REPOSITORY_RE.match(value)
    if match is None:
        return None
    return match.group("owner"), match.group("repo")


def _lookup_repository(ctx: OperationContext, *, repository: str, owner: str, repo: str) -> dict[str, object] | OperationOutcome:
    try:
        command = ctx.command(
            [
                "gh",
                "api",
                "graphql",
                "-f",
                "query=query($owner:String!,$repo:String!){repository(owner:$owner,name:$repo){id nameWithOwner}}",
                "-f",
                f"owner={owner}",
                "-f",
                f"repo={repo}",
            ],
            failures={"os_error": "create_blocked", "nonzero": "create_blocked"},
        )
    except MappedOutcomeError as exc:
        outcome = exc.outcome
        text = f"{outcome.raw.get('stderr', '')}\n{outcome.raw.get('stdout', '')}".lower()
        if outcome.status == "create_blocked" and (
            "could not resolve to a repository" in text or "repository not found" in text or "not found" in text
        ):
            return fail(
                code="repository_not_found",
                summary="GitHub repository was not found",
                diagnostics=(
                    Diagnostic(
                        code="action.gh_issue_create.repository_not_found",
                        level="error",
                        message="GitHub repository was not found",
                        details={"reference": ctx.reference, "repository": repository},
                    ),
                ),
                raw=outcome.raw,
            )
        return fail(
            code="create_blocked",
            summary="Inspecting GitHub repository failed",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_create.repository_lookup_failed",
                    level="error",
                    message="Inspecting GitHub repository failed",
                    details={"reference": ctx.reference, "repository": repository},
                ),
            ),
            raw=outcome.raw,
        )

    try:
        payload = json.loads(command.stdout) if command.stdout else {}
    except json.JSONDecodeError as exc:
        return fail(
            code="create_blocked",
            summary="GitHub repository output was not valid JSON",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_create.repository_invalid_json",
                    level="error",
                    message="GitHub repository output was not valid JSON",
                    details={"reference": ctx.reference, "repository": repository, "error": str(exc)},
                ),
            ),
            raw=command.raw,
        )

    repository_data = ((payload.get("data") or {}).get("repository"))
    if repository_data is None:
        return fail(
            code="repository_not_found",
            summary="GitHub repository was not found",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_create.repository_not_found",
                    level="error",
                    message="GitHub repository was not found",
                    details={"reference": ctx.reference, "repository": repository},
                ),
            ),
            raw=command.raw,
        )
    if not isinstance(repository_data, dict):
        return fail(
            code="create_blocked",
            summary="GitHub repository output was not an object",
            diagnostics=(
                Diagnostic(
                    code="action.gh_issue_create.repository_invalid_shape",
                    level="error",
                    message="GitHub repository output was not an object",
                    details={"reference": ctx.reference, "repository": repository},
                ),
            ),
            raw=command.raw,
        )
    return {"raw": command.raw, "repository": repository_data}


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
