"""Submit one GitHub Actions workflow-dispatch request."""

from __future__ import annotations

import json
import re
import subprocess

from connectors.gh._repository import REPOSITORY_INPUTS, resolve_repository_target
from ordo.model.human import declare_human
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, action, fail


OUTPUTS = {
    "repository": "string | null", "workflow": "string | null", "ref": "string | null", "request_id": "string | null",
    "submission": "string", "run_id": "integer | null", "url": "string | null",
    "http_status": "integer | null", "message": "string | null", "errors": "array | object | string | null",
}
_WORKFLOW = re.compile(r"(?:[1-9][0-9]*|[A-Za-z0-9][A-Za-z0-9._-]*\.ya?ml)")
_INPUT_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")


HUMAN = declare_human({
    "title": "GitHub actions dispatch",
    "goal": "Start one workflow that is configured for manual dispatch on a chosen branch or tag.",
    "summary": "Submit one manual workflow start request with a ref and named input values.",
    "sections": [
        {"heading": "Use when", "items": [
            "The workflow already supports manual dispatch and the surrounding workflow has explicitly decided to start it.",
            "Provide the workflow file name or its positive numeric ID, the branch or tag ref to use, and at most 25 named input values.",
            "A submitted result confirms only that GitHub accepted the start request. It does not confirm that the workflow completed successfully.",
        ]},
        {"heading": "What to provide", "items": [
            "`workflow`: required; use a workflow file name ending in .yml or .yaml, or its positive numeric ID.",
            "`ref`: required; use a nonblank branch or tag name without control characters.",
            "`inputs`: required object; each key is a workflow input name and each value is a string, number, or boolean. Omit no required workflow inputs.",
            "`request_id`: required; provide the correlation value that the workflow puts in its run name. It is sent as the request_id workflow input.",
            "`repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide another OWNER/REPO to override that target for this request.",
        ]},
        {"heading": "Result and boundary", "items": [
            "The result includes `repository`, `workflow`, `ref`, `request_id`, `submission`, `run_id`, `url`, `message`, and `errors`. `submission=submitted` confirms acceptance. When GitHub returns a run identity, `run_id` and `url` identify that run; they can otherwise be null.",
            "`dispatch_refused` confirms that GitHub rejected the request. `dispatch_unknown` confirms neither submission nor non-submission; inspect before deciding whether to submit again.",
            "This action does not wait, poll, rerun, cancel, or judge the dispatched workflow.",
        ]},
        {"heading": "Do not use for", "items": [
            "Observing an existing Actions run or its jobs; use gh.actions.run and gh.actions.run.jobs.",
            "Automatically retrying an unknown submission result.",
        ]},
        {"heading": "Related references", "body": "Use these related references when the workflow needs to inspect Actions state before or after submission.", "references": [
            {"handle": "connector.gh.actions.run.search", "summary": "Find every run whose complete name equals this request ID when GitHub did not return a run identity."},
            {"handle": "connector.gh.actions.run", "summary": "Observe one known Actions run after its identity is available."},
            {"handle": "connector.gh.actions.run.jobs", "summary": "Observe all jobs for one identified Actions run attempt."},
            {"handle": "connector.gh.repo.actions.permissions", "summary": "Inspect whether repository Actions are enabled before a hosted workflow change."},
        ]},
        {"heading": "Inspect next", "items": ["connector.gh.actions.run.search", "connector.gh.actions.run", "connector.gh.actions.run.jobs"]},
    ],
})


def info():
    return action(
        name="actions.dispatch",
        human=HUMAN,
        summary="Submit one manual GitHub Actions workflow start request; acceptance is not completion.",
        inputs={**REPOSITORY_INPUTS, "workflow": "string", "ref": "string", "inputs": "object", "request_id": "string"},
        outputs=OUTPUTS,
        effects=("submit one GitHub Actions workflow-dispatch request",),
        failure_modes=("input_error", "dispatch_refused", "dispatch_unknown"),
        invalidates_observations=("gh.actions.*",),
        examples=({"reference": "gh.actions.dispatch", "inputs": {
            "workflow": "deploy.yml", "ref": "main", "inputs": {"dry_run": True}, "request_id": "deploy-42",
        }},),
        handler=run,
    )


def _failure(ctx, code, message, outputs, raw):
    return fail(code=code, summary=message, outputs=outputs, raw=raw, diagnostics=(Diagnostic(
        code=f"action.gh_actions_dispatch.{code}", level="error", message=message,
        details={"reference": ctx.reference, "phase": raw["phase"]},
    ),))


def _response(stdout):
    header, separator, body = stdout.replace("\r\n", "\n").partition("\n\n")
    lines = header.splitlines()
    match = re.fullmatch(r"HTTP/\d(?:\.\d)? ([1-5][0-9]{2})(?: .*)?", lines[0] if lines else "")
    if not separator or match is None or any(
        re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+:.*", line) is None for line in lines[1:]
    ):
        raise ValueError("missing or malformed HTTP response")
    status = int(match[1])
    if status == 204 and body == "":
        return status, None
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise ValueError("response is not a JSON object")
    return status, payload


def _validate(ctx):
    target = resolve_repository_target(ctx, failure_code="input_error", diagnostic_prefix="action.gh_actions_dispatch")
    if isinstance(target, OperationOutcome):
        raise MappedOutcomeError(target)
    workflow, ref, inputs, request_id = ctx.input("workflow"), ctx.input("ref"), ctx.input("inputs"), ctx.input("request_id")
    if not isinstance(workflow, str) or _WORKFLOW.fullmatch(workflow) is None:
        raise ValueError("workflow must be a positive numeric ID or a workflow file name ending in .yml or .yaml")
    if not isinstance(ref, str) or not ref.strip() or any(ord(char) < 32 or ord(char) == 127 for char in ref):
        raise ValueError("ref must be a nonblank branch or tag name without control characters")
    if not isinstance(inputs, dict) or len(inputs) > 25:
        raise ValueError("inputs must be an object with at most 25 properties")
    for name, value in inputs.items():
        if not isinstance(name, str) or _INPUT_NAME.fullmatch(name) is None:
            raise ValueError("each input name must start with a letter or underscore and contain only letters, digits, hyphens, or underscores")
        if isinstance(value, (dict, list)) or value is None:
            raise ValueError("each input value must be a string, number, or boolean")
        if not isinstance(value, (str, int, float, bool)) or isinstance(value, float) and not value.isfinite():
            raise ValueError("each input value must be a finite string, number, or boolean")
    if "request_id" in inputs or not isinstance(request_id, str) or not request_id or any(ord(char) < 32 for char in request_id):
        raise ValueError("request_id must be a nonblank string without control characters and cannot also appear in inputs")
    return target, workflow, ref, inputs, request_id


def run(ctx: OperationContext) -> OperationOutcome:
    outputs = dict.fromkeys(OUTPUTS)
    outputs["submission"] = "unknown"
    raw = {"phase": "input"}
    try:
        target, workflow, ref, inputs, request_id = _validate(ctx)
    except MappedOutcomeError as exc:
        return _failure(ctx, "input_error", exc.outcome.summary, outputs, raw)
    except ValueError as exc:
        return _failure(ctx, "input_error", str(exc), outputs, raw)
    outputs.update(repository=target.repository, workflow=workflow, ref=ref, request_id=request_id)
    argv = [
        "gh", "api", "--hostname", "github.com", "--method", "POST", "--include",
        f"/repos/{target.repository}/actions/workflows/{workflow}/dispatches",
        "-H", "Accept: application/vnd.github+json", "-H", "X-GitHub-Api-Version: 2026-03-10",
        "-F", f"ref={ref}",
    ]
    for name, value in inputs.items():
        flag = "-f" if isinstance(value, str) else "-F"
        encoded = str(value).lower() if isinstance(value, bool) else value
        argv.extend([flag, f"inputs[{name}]={encoded}"])
    argv.extend(["-f", f"inputs[request_id]={request_id}"])
    raw["phase"] = "dispatch"
    try:
        command = ctx.command(argv, failures={"os_error": "dispatch_unknown", "nonzero": "dispatch_unknown"})
        stdout = command.stdout
    except MappedOutcomeError as exc:
        raw["command_error"] = exc.outcome.status
        stdout = exc.outcome.raw.get("stdout", "")
    except (subprocess.TimeoutExpired, OSError, UnicodeError) as exc:
        raw["command_error"] = type(exc).__name__
        stdout = ""
    try:
        status, payload = _response(stdout)
        outputs["http_status"] = status
        if payload is not None:
            outputs["message"] = payload.get("message") if isinstance(payload.get("message"), str) else None
            outputs["errors"] = payload.get("errors")
        if status in (200, 204):
            if status == 200:
                run_id, url = payload.get("workflow_run_id"), payload.get("html_url")
                if type(run_id) is not int or run_id <= 0 or not isinstance(url, str) or not url:
                    raise ValueError("accepted response lacks a valid workflow run identity")
                outputs.update(run_id=run_id, url=url)
            outputs["submission"] = "submitted"
            return OperationOutcome(status="ok", summary="GitHub Actions workflow dispatch submitted", outputs=outputs,
                                    diagnostics=target.diagnostics, raw=raw)
        if status in (400, 401, 403, 404, 422):
            outputs["submission"] = "refused"
            return _failure(ctx, "dispatch_refused", "GitHub refused the workflow dispatch request", outputs, raw)
    except (ValueError, TypeError, AttributeError, json.JSONDecodeError):
        raw["response_error"] = "invalid_or_untrusted_response"
    return _failure(ctx, "dispatch_unknown", "Workflow dispatch result is unknown; do not blindly retry", outputs, raw)
