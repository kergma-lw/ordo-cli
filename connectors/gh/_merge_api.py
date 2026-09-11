"""HTTP response handling shared only by the asynchronous PR merge operations."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass

from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, fail

MERGE_OUTPUTS = {
    "repository": "string", "pull_number": "integer", "request_id": "string",
    "state": "string", "merged": "boolean", "merge_sha": "string",
    "merge_method": "string", "merge_action": "string", "expected_head_sha": "string",
    "http_status": "integer", "message": "string",
}


def full_sha(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{40}", value) is not None


def request_uuid(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(
        r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", value
    ) is not None


@dataclass(frozen=True)
class MergeResponse:
    http_status: int | None
    payload: dict
    raw: dict

    @property
    def details(self) -> dict:
        value = self.payload.get("details")
        return value if isinstance(value, dict) else {}

    @property
    def message(self) -> str:
        value = self.details.get("message", self.payload.get("message"))
        return value if isinstance(value, str) else str(self.raw.get("stderr") or "")


def merge_api(ctx: OperationContext, endpoint: str, *, fields: dict[str, str] | None = None) -> MergeResponse:
    """Make exactly one CLI call, retaining HTTP errors even when gh exits nonzero."""
    argv = ["gh", "api", endpoint, "--method", "GET" if fields is None else "PUT", "--include",
            "-H", "Accept: application/vnd.github+json", "-H", "X-GitHub-Api-Version: 2026-03-10"]
    for key, value in (fields or {}).items():
        argv.extend(["-f", f"{key}={value}"])
    try:
        command = ctx.command(argv, failures={"os_error": "merge_transport_error", "nonzero": "merge_http_error"})
        stdout, raw = command.stdout, command.raw
    except MappedOutcomeError as exc:
        raw = exc.outcome.raw
        stdout = str(raw.get("stdout") or "")
    except subprocess.TimeoutExpired as exc:
        return MergeResponse(None, {}, {
            "argv": argv, "stdout": str(exc.stdout or ""), "stderr": str(exc.stderr or ""),
            "timeout": str(exc),
        })
    # --include is necessary: 409 means an existing async request, not a SHA mismatch.
    text = stdout.replace("\r\n", "\n")
    match = re.match(r"HTTP/\S+\s+(\d{3})[^\n]*\n", text)
    status = int(match[1]) if match else None
    body = text.partition("\n\n")[2] if match else ""
    try:
        payload = json.loads(body)
    except (ValueError, TypeError):
        payload = {}
    return MergeResponse(status, payload if isinstance(payload, dict) else {}, dict(raw))


def response_outputs(identity, response: MergeResponse) -> dict:
    details = response.details
    state = response.payload.get("status")
    known = valid_async_payload(response) and (
        response.http_status == 200
        or (response.http_status in (202, 409) and state == "pending")
    )
    return {
        "repository": identity.repository, "pull_number": identity.pull_number,
        "request_id": details.get("uuid") if request_uuid(details.get("uuid")) else None,
        "state": state if isinstance(state, str) else "unknown",
        "merged": (state == "merged") if known else None,
        "merge_sha": details.get("sha") if known and state == "merged" else None,
        "merge_method": details.get("merge_method"), "merge_action": details.get("merge_action"),
        "expected_head_sha": details.get("expected_head_sha"),
        "http_status": response.http_status, "message": response.message,
    }


def valid_async_payload(response: MergeResponse, *, request_id: str | None = None) -> bool:
    """Validate documented discriminated async states, including pending details."""
    state, details = response.payload.get("status"), response.details
    if not isinstance(state, str) or not isinstance(details.get("message"), str):
        return False
    if state == "pending":
        return (request_uuid(details.get("uuid"))
                and (request_id is None or details["uuid"].lower() == request_id.lower())
                and details.get("merge_method") in ("default", "merge", "squash", "rebase")
                and details.get("merge_action") in ("default", "direct_merge", "merge_queue")
                and full_sha(details.get("expected_head_sha")))
    if state == "merged":
        return full_sha(details.get("sha"))
    return state in ("failed", "enqueued")


def merge_failure(ctx, code: str, summary: str, *, outputs=None, raw=None):
    return fail(
        code=code, summary=summary, outputs=outputs, raw=raw,
        diagnostics=(Diagnostic(code=f"{ctx.reference}.{code}", level="error", message=summary,
                                details={"reference": ctx.reference, **(outputs or {})}),),
    )
