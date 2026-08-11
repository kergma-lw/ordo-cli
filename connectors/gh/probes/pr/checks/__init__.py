"""gh.pr.checks probe."""

from __future__ import annotations

import json

from connectors.gh._external import fail_github_command
from connectors.gh._pull_identity import PULL_IDENTITY_INPUTS, resolve_pull_identity
from connectors.gh.probes.pr._shared import fetch_pull_request
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, fail, ok, probe

_FAILED_CONCLUSIONS = {"failure", "failed", "error", "cancelled", "timed_out", "action_required", "startup_failure", "stale"}
_SUCCESS_CONCLUSIONS = {"success", "neutral", "skipped"}


def info():
    return probe(
        name="pr.checks",
        summary="Read normalized status and check-run results from a GitHub pull request head.",
        inputs=PULL_IDENTITY_INPUTS,
        outputs={
            "pull_ref": "string",
            "head_sha": "string",
            "overall_state": "string",
            "total_count": "integer",
            "success_count": "integer",
            "failed_count": "integer",
            "pending_count": "integer",
            "skipped_count": "integer",
            "checks": [
                {
                    "name": "string",
                    "kind": "string",
                    "status": "string",
                    "conclusion": "string",
                    "context": "string",
                    "url": "string",
                }
            ],
        },
        failure_modes=("pull_not_found", "checks_unavailable", "probe_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    identity = resolve_pull_identity(ctx, failure_code="probe_failed", diagnostic_prefix="probe.gh_pr_checks")
    if isinstance(identity, OperationOutcome):
        return identity
    fetched_pull = fetch_pull_request(ctx, identity=identity, diagnostic_prefix="probe.gh_pr_checks")
    if isinstance(fetched_pull, OperationOutcome):
        return fetched_pull
    pull_payload, pull_raw = fetched_pull
    head = pull_payload.get("head")
    head_sha = (head or {}).get("sha") if isinstance(head, dict) else None
    if not isinstance(head_sha, str) or not head_sha:
        return fail(
            code="checks_unavailable",
            summary="GitHub pull request head SHA was unavailable for checks inspection",
            diagnostics=(
                Diagnostic(
                    code="probe.gh_pr_checks.missing_head_sha",
                    level="error",
                    message="GitHub pull request head SHA was unavailable for checks inspection",
                    details={"reference": ctx.reference, "pull_ref": identity.pull_ref},
                ),
            ),
            raw={"pull": pull_raw},
        )

    status_result = _fetch_statuses(ctx, identity=identity, head_sha=head_sha)
    if isinstance(status_result, OperationOutcome):
        return status_result
    statuses_payload, statuses_raw = status_result

    check_run_result = _fetch_check_runs(ctx, identity=identity, head_sha=head_sha)
    if isinstance(check_run_result, OperationOutcome):
        return check_run_result
    check_runs_payload, check_runs_raw = check_run_result

    checks = [*_normalize_statuses(statuses_payload), *_normalize_check_runs(check_runs_payload)]
    success_count, failed_count, pending_count, skipped_count = _classify_counts(checks)
    return ok(
        summary="GitHub pull request checks retrieved successfully",
        outputs={
            "pull_ref": identity.pull_ref,
            "head_sha": head_sha,
            "overall_state": _overall_state(checks, failed_count=failed_count, pending_count=pending_count),
            "total_count": len(checks),
            "success_count": success_count,
            "failed_count": failed_count,
            "pending_count": pending_count,
            "skipped_count": skipped_count,
            "checks": checks,
        },
        raw={"pull": pull_raw, "statuses": statuses_raw, "check_runs": check_runs_raw},
    )


def _fetch_statuses(
    ctx: OperationContext,
    *,
    identity,
    head_sha: str,
) -> tuple[dict[str, object], dict[str, object]] | OperationOutcome:
    try:
        command = ctx.command(
            ["gh", "api", f"repos/{identity.owner}/{identity.repo}/commits/{head_sha}/status"],
            failures={"os_error": "probe_failed"},
        )
    except MappedOutcomeError as exc:
        return _checks_command_failure(ctx, exc.outcome, pull_ref=identity.pull_ref, diagnostic_code="probe.gh_pr_checks.statuses_failed")
    return _parse_object_payload(ctx, command.stdout, command.raw, pull_ref=identity.pull_ref, diagnostic_code="probe.gh_pr_checks.statuses_invalid_json")


def _fetch_check_runs(
    ctx: OperationContext,
    *,
    identity,
    head_sha: str,
) -> tuple[dict[str, object], dict[str, object]] | OperationOutcome:
    try:
        command = ctx.command(
            ["gh", "api", f"repos/{identity.owner}/{identity.repo}/commits/{head_sha}/check-runs"],
            failures={"os_error": "probe_failed"},
        )
    except MappedOutcomeError as exc:
        return _checks_command_failure(ctx, exc.outcome, pull_ref=identity.pull_ref, diagnostic_code="probe.gh_pr_checks.check_runs_failed")
    return _parse_object_payload(ctx, command.stdout, command.raw, pull_ref=identity.pull_ref, diagnostic_code="probe.gh_pr_checks.check_runs_invalid_json")


def _parse_object_payload(
    ctx: OperationContext,
    stdout: str,
    raw: dict[str, object],
    *,
    pull_ref: str,
    diagnostic_code: str,
) -> tuple[dict[str, object], dict[str, object]] | OperationOutcome:
    try:
        payload = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError as exc:
        return fail(
            code="checks_unavailable",
            summary="GitHub pull request checks were unavailable",
            diagnostics=(
                Diagnostic(
                    code=diagnostic_code,
                    level="error",
                    message="GitHub pull request checks were unavailable",
                    details={"reference": ctx.reference, "pull_ref": pull_ref, "error": str(exc)},
                ),
            ),
            raw=raw,
        )
    if not isinstance(payload, dict):
        return fail(
            code="checks_unavailable",
            summary="GitHub pull request checks were unavailable",
            diagnostics=(
                Diagnostic(
                    code=f"{diagnostic_code}.shape",
                    level="error",
                    message="GitHub pull request checks were unavailable",
                    details={"reference": ctx.reference, "pull_ref": pull_ref},
                ),
            ),
            raw=raw,
        )
    return payload, raw


def _checks_command_failure(ctx: OperationContext, outcome: OperationOutcome, *, pull_ref: str, diagnostic_code: str) -> OperationOutcome:
    return fail_github_command(
        ctx,
        code="checks_unavailable",
        summary="GitHub pull request checks were unavailable",
        raw=outcome.raw,
        diagnostic_code=diagnostic_code,
        details={"pull_ref": pull_ref},
        message="GitHub pull request checks were unavailable",
    )


def _normalize_statuses(payload: dict[str, object]) -> list[dict[str, object]]:
    statuses = payload.get("statuses")
    if not isinstance(statuses, list):
        return []
    items: list[dict[str, object]] = []
    for status in statuses:
        if not isinstance(status, dict):
            continue
        state = str(status.get("state") or "")
        items.append(
            {
                "name": status.get("context") or status.get("description") or "status",
                "kind": "status",
                "status": "pending" if state == "pending" else "completed",
                "conclusion": None if state == "pending" else ("failure" if state == "error" else state),
                "context": status.get("context"),
                "url": status.get("target_url"),
            }
        )
    return items


def _normalize_check_runs(payload: dict[str, object]) -> list[dict[str, object]]:
    runs = payload.get("check_runs")
    if not isinstance(runs, list):
        return []
    items: list[dict[str, object]] = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        items.append(
            {
                "name": run.get("name"),
                "kind": "check_run",
                "status": run.get("status"),
                "conclusion": run.get("conclusion"),
                "context": None,
                "url": run.get("html_url") or ((run.get("details_url") if isinstance(run.get("details_url"), str) else None)),
            }
        )
    return items


def _classify_counts(checks: list[dict[str, object]]) -> tuple[int, int, int, int]:
    success = 0
    failed = 0
    pending = 0
    skipped = 0
    for check in checks:
        status = check.get("status")
        conclusion = check.get("conclusion")
        if status not in {"completed", "success"} and conclusion is None:
            pending += 1
            continue
        if conclusion == "skipped":
            skipped += 1
            continue
        if isinstance(conclusion, str) and conclusion in _FAILED_CONCLUSIONS:
            failed += 1
            continue
        if isinstance(conclusion, str) and conclusion in _SUCCESS_CONCLUSIONS:
            success += 1
            continue
        if status in {"queued", "in_progress", "pending", None}:
            pending += 1
            continue
        success += 1
    return success, failed, pending, skipped


def _overall_state(checks: list[dict[str, object]], *, failed_count: int, pending_count: int) -> str:
    if failed_count > 0:
        return "failed"
    if pending_count > 0:
        return "pending"
    if not checks:
        return "no_checks"
    return "success"
