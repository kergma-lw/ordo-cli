"""Create one GitHub.com PR after a complete public open-list duplicate guard.

The guard is not atomic. A racing 422 remains a refusal, never reuse or success.
Preflight metadata is advisory: its placeholders cannot derive a source owner.
"""

from __future__ import annotations

import json
import re
import subprocess

from connectors.gh._pr_create_contract import branch, created_item, matches, repository
from connectors.gh._repository import resolve_repository_target
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, action, fail, preflight_observation


OUTPUTS = {
    "repository": "string | null", "pull_number": "integer | null", "pull_ref": "string | null",
    "url": "string | null", "created": "boolean | null",
    "head_repository": "string | null", "head_ref": "string | null", "head_sha": "string | null",
    "base_repository": "string | null", "base_ref": "string | null", "base_sha": "string | null",
    "draft": "boolean | null", "state": "string | null", "http_status": "integer | null",
    "message": "string | null", "errors": "array | object | string | null",
}
_MISSING = object()


def info():
    return action(
        name="pr.create",
        summary="Create one PR with explicit draft and exact source repository after a complete gh.pr.list open guard; creation_unknown must not be blindly retried.",
        inputs={"repository": "string", "head": "string", "base": "string", "title": "string",
                "body": "string", "draft": "boolean", "head_repository": "string", "head_owner": "string"},
        outputs=OUTPUTS,
        effects=("create one GitHub pull request after a non-atomic open duplicate precheck",),
        failure_modes=("input_error", "precheck_failed", "ambiguous", "already_exists", "api_failed", "create_refused", "creation_unknown"),
        invalidates_observations=("gh.*",),
        preflight_observations=(preflight_observation(
            probe="gh.pr.list", with_={"repository": "{repository}", "head": "{head}",
                                      "base": "{base}", "state": "open"},
            fields=("items", "count", "complete"),
        ),),
        handler=run,
    )


def _optional(ctx, name, default=_MISSING):
    try:
        return ctx.input(name)
    except MappedOutcomeError as exc:
        if exc.outcome.status != "input_error":
            raise
        return default


def _failure(ctx, code, message, outputs, raw):
    return fail(code=code, summary=message, outputs=outputs, raw=raw, diagnostics=(Diagnostic(
        code=f"action.gh_pr_create.{code}", level="error", message=message,
        details={"reference": ctx.reference, "phase": raw["phase"]},
    ),))


def _observed(outputs, item):
    outputs.update({key: item.get(key) for key in (
        "pull_ref", "url", "head_repository", "head_ref", "head_sha", "base_repository", "base_ref", "base_sha", "draft", "state",
    )})
    outputs["pull_number"] = item["number"]


def run(ctx: OperationContext) -> OperationOutcome:
    outputs = dict.fromkeys(OUTPUTS)
    outputs["created"] = False
    raw = {"phase": "input"}
    try:
        target = resolve_repository_target(ctx, failure_code="input_error", diagnostic_prefix="action.gh_pr_create")
        if isinstance(target, OperationOutcome):
            return _failure(ctx, "input_error", target.summary, outputs, raw)
        repo = target.repository
        if not repository(repo):
            raise ValueError("Resolved repository must use safe OWNER/REPO with a GitHub owner name")
        source = _optional(ctx, "head_repository", repo)
        if not repository(source):
            raise ValueError("head_repository must be an exact safe OWNER/REPO")
        owner = source.split("/")[0]
        asserted_owner = _optional(ctx, "head_owner", owner)
        if (not isinstance(asserted_owner, str) or asserted_owner.lower() != owner.lower()):
            raise ValueError("head_owner must match head_repository owner; supply exact head_repository for another source owner")
        head, base, title, draft = (ctx.input(key) for key in ("head", "base", "title", "draft"))
        body = _optional(ctx, "body", "")
        if not branch(head) or not branch(base):
            raise ValueError("head and base must be nonempty branch refs without whitespace, controls, or colon")
        if not isinstance(title, str) or not title.strip() or "\x00" in title:
            raise ValueError("title must be a nonblank string without NUL")
        if not isinstance(body, str) or "\x00" in body or type(draft) is not bool:
            raise ValueError("body must be a string and draft must be an explicit boolean")
        if source.lower() == repo.lower() and head == base:
            raise ValueError("head and base must differ within the same repository")
    except MappedOutcomeError as exc:
        return _failure(ctx, exc.outcome.status, exc.outcome.summary, outputs, raw)
    except ValueError as exc:
        return _failure(ctx, "input_error", str(exc), outputs, raw)
    outputs.update(repository=repo, head_repository=source, head_ref=head,
                   base_repository=repo, base_ref=base, draft=draft)
    inputs = {"repository": repo, "head": head, "head_owner": owner, "base": base, "state": "open"}
    raw["phase"] = "precheck"
    try:
        before = ctx.call("gh.pr.list", inputs=inputs)
        raw["precheck"] = {"status": before.status}
        existing = matches(before, inputs, source)
    except (MappedOutcomeError, subprocess.TimeoutExpired, OSError, UnicodeError) as exc:
        raw["command_error"] = type(exc).__name__
        return _failure(ctx, "precheck_failed", "Open PR precheck failed; no creation submitted", outputs, raw)
    except ValueError as exc:
        return _failure(ctx, "precheck_failed", str(exc), outputs, raw)
    if len(existing) > 1:
        return _failure(ctx, "ambiguous", "Multiple open pull requests match the exact source and target identity", outputs, raw)
    if existing:
        _observed(outputs, existing[0])
        return _failure(ctx, "already_exists", "An open pull request already matches the exact identity", outputs, raw)

    argv = ["gh", "api", "--hostname", "github.com", "--method", "POST", "--include",
            f"/repos/{repo}/pulls", "-H", "Accept: application/vnd.github+json",
            "-H", "X-GitHub-Api-Version: 2026-03-10"]
    fields = {"head": head if source.lower() == repo.lower() else f"{owner}:{head}",
              "base": base, "title": title, "body": body}
    if source.lower() != repo.lower():
        fields["head_repo"] = source.split("/")[1]
    for key, value in fields.items():
        argv.extend(["-f", f"{key}={value}"])
    argv.extend(["-F", f"draft={str(draft).lower()}"])
    raw["phase"] = "create"
    outputs["created"] = None
    try:
        command = ctx.command(argv, failures={"os_error": "creation_unknown", "nonzero": "creation_unknown"})
        stdout = command.stdout
    except MappedOutcomeError as exc:
        raw["command_error"] = exc.outcome.status
        stdout = exc.outcome.raw.get("stdout", "")
    except (subprocess.TimeoutExpired, OSError, UnicodeError) as exc:
        raw["command_error"] = type(exc).__name__
        stdout = ""
    # Retain phase/status, not command argv, stdout, stderr, title or body: those
    # may contain credentials or private text. API errors are structured outputs.
    try:
        header, separator, body_text = stdout.replace("\r\n", "\n").partition("\n\n")
        lines = header.split("\n")
        status = re.fullmatch(r"HTTP/\d(?:\.\d)? (\d{3})(?: .*)?", lines[0])
        if not separator or not status or any(not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+:.*", line) for line in lines[1:]):
            raise ValueError("Missing or malformed HTTP response")
        outputs["http_status"] = int(status[1])
        payload = json.loads(body_text)
        if not isinstance(payload, dict):
            raise ValueError("Response is not a JSON object")
        outputs["message"] = payload.get("message") if isinstance(payload.get("message"), str) else None
        outputs["errors"] = payload.get("errors")
        if outputs["http_status"] in (400, 401, 403, 404, 409, 422):
            outputs["created"] = False
            code = "api_failed" if outputs["http_status"] in (401, 403, 404) else "create_refused"
            return _failure(ctx, code, "GitHub refused PR creation", outputs, raw)
        if outputs["http_status"] == 201:
            item = created_item(payload, repo, source, head, base, draft, title)
            _observed(outputs, item)
            outputs["created"] = True
            return OperationOutcome(status="ok", summary="Created GitHub pull request", outputs=outputs,
                                    diagnostics=target.diagnostics, raw=raw)
    except (ValueError, TypeError, AttributeError, RecursionError):
        raw["response_error"] = "invalid_or_untrusted_response"
    return _failure(ctx, "creation_unknown", "PR creation result is unknown; do not blindly retry", outputs, raw)
