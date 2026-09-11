"""Observe API-attached PR checks without deciding workflow acceptance policy."""

from __future__ import annotations

import json
import re

from connectors.gh._external import fail_github_command
from connectors.gh._pull_identity import PULL_IDENTITY_INPUTS, resolve_pull_identity
from connectors.gh.probes.pr import observation_metadata, observe_test_merge, validate_observation_identity
from connectors.gh.probes.pr._shared import fetch_pull_request
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, fail, ok, probe

_FAILED_CONCLUSIONS = {"failure", "failed", "error", "cancelled", "timed_out", "action_required", "startup_failure", "stale"}
_PENDING_STATUSES = {"queued", "in_progress", "pending", "requested", "waiting", "pending_deployment"}


def info():
    return probe(
        name="pr.checks",
        summary="Observe paginated API-attached checks for a PR head or verified test merge; optionally bind expected_head_sha.",
        inputs={**PULL_IDENTITY_INPUTS, "target": "string", "expected_head_sha": "string"},
        outputs={
            "pull_ref": "string",
            "head_sha": "string",
            "base_sha": "string",
            "head_repository": "string",
            "base_repository": "string",
            "target": "string",
            "expected_head_sha": "string",
            "commit_sha": "string",
            "test_merge_sha": "string",
            "test_merge_head_sha": "string",
            "test_merge_base_sha": "string",
            "test_merge_state": "string",
            "test_merge_reason": "string",
            "sha_evidence": "string",
            "complete": "boolean",
            "statuses_complete": "boolean",
            "check_runs_complete": "boolean",
            "overall_state": "string",
            "total_count": "integer",
            "success_count": "integer",
            "failed_count": "integer",
            "pending_count": "integer",
            "skipped_count": "integer",
            "neutral_count": "integer",
            "unknown_count": "integer",
            "checks": [{
                "name": "string", "kind": "string", "status": "string",
                "conclusion": "string", "state": "string", "context": "string",
                "url": "string", "sha": "string", "sha_source": "string",
                "id": "integer", "created_at": "string", "updated_at": "string",
                "started_at": "string", "completed_at": "string",
                "app_id": "integer", "app_slug": "string",
                "app_identity": "string", "creator": "object",
            }],
        },
        failure_modes=("pull_not_found", "checks_unavailable", "probe_failed"),
        handler=run,
    )


def _optional_input(ctx: OperationContext, name: str, default=None):
    try:
        return ctx.input(name)
    except MappedOutcomeError as exc:
        return default if exc.outcome.status == "input_error" else exc.outcome


def _unavailable(ctx, reason, message, *, raw=None, outputs=None):
    return fail(
        code="checks_unavailable", summary=message,
        diagnostics=(Diagnostic(code=f"probe.gh_pr_checks.{reason}", level="error",
                                message=message, details={"reference": ctx.reference}),),
        raw=raw or {}, outputs=outputs or {},
    )


def run(ctx: OperationContext) -> OperationOutcome:
    target = _optional_input(ctx, "target", "head")
    expected = _optional_input(ctx, "expected_head_sha")
    for value in (target, expected):
        if isinstance(value, OperationOutcome):
            return value
    if target not in ("head", "test_merge"):
        return _unavailable(ctx, "invalid_target", "Checks target must be head or test_merge")
    if expected is not None and (not isinstance(expected, str) or re.fullmatch(r"[0-9a-fA-F]{40}", expected) is None):
        return _unavailable(ctx, "invalid_expected_head_sha", "expected_head_sha must be a full 40-character commit SHA")
    if expected is not None:
        expected = expected.lower()
    identity = resolve_pull_identity(ctx, failure_code="probe_failed", diagnostic_prefix="probe.gh_pr_checks")
    if isinstance(identity, OperationOutcome):
        return identity
    fetched = fetch_pull_request(ctx, identity=identity, diagnostic_prefix="probe.gh_pr_checks")
    if isinstance(fetched, OperationOutcome):
        return fetched
    payload, pull_raw = fetched
    invalid_identity = validate_observation_identity(ctx, identity=identity, payload=payload, raw=pull_raw)
    if invalid_identity is not None:
        return invalid_identity
    head = payload.get("head") if isinstance(payload.get("head"), dict) else {}
    head_sha = head.get("sha")
    metadata = observation_metadata(payload)
    outputs = {
        "pull_ref": identity.pull_ref, "head_sha": head_sha,
        "base_sha": metadata["base_sha"], "head_repository": metadata["head_repository"],
        "base_repository": metadata["base_repository"], "target": target,
        "expected_head_sha": expected, "commit_sha": None,
        "test_merge_sha": None, "test_merge_head_sha": None,
        "test_merge_base_sha": None, "test_merge_state": "not_requested",
        "test_merge_reason": "not_requested",
        "sha_evidence": "api_attached_commit", "complete": False,
    }
    raw = {"pull": pull_raw}
    if not isinstance(head_sha, str) or not head_sha:
        return _unavailable(ctx, "missing_head_sha", "GitHub pull request head SHA was unavailable for checks inspection", raw=raw, outputs=outputs)
    if expected is not None and expected != head_sha.lower():
        return _unavailable(ctx, "head_mismatch", "GitHub pull request head differs from expected_head_sha", raw=raw, outputs=outputs)
    commit_sha = head_sha
    if target == "test_merge":
        candidate = observe_test_merge(ctx, identity=identity, payload=payload)
        candidate_outputs, candidate_raw = candidate
        outputs.update(candidate_outputs)
        raw["test_merge"] = candidate_raw
        if outputs["test_merge_state"] != "verified":
            return _unavailable(ctx, "test_merge_unavailable", "A test merge tied to the observed base and head was unavailable", raw=raw, outputs=outputs)
        commit_sha = outputs["test_merge_sha"]
    outputs["commit_sha"] = commit_sha

    statuses_result = _fetch_pages(ctx, identity=identity, commit_sha=commit_sha, kind="statuses")
    if isinstance(statuses_result, OperationOutcome):
        return statuses_result
    runs_result = _fetch_pages(ctx, identity=identity, commit_sha=commit_sha, kind="check_runs")
    if isinstance(runs_result, OperationOutcome):
        return runs_result
    status_pages, statuses_raw, statuses_complete = statuses_result
    run_pages, runs_raw, runs_complete = runs_result
    checks = [
        *(item for page in status_pages for item in _normalize_statuses(page)),
        *(item for page in run_pages for item in _normalize_check_runs(page)),
    ]
    raw.update(statuses=statuses_raw, check_runs=runs_raw)
    if any(item["sha"] is not None and item["sha"] != commit_sha for item in checks):
        return _unavailable(ctx, "check_sha_mismatch", "GitHub returned checks attached to a different commit", raw=raw, outputs=outputs)
    complete = statuses_complete and runs_complete
    counts = {name: 0 for name in ("success", "failed", "pending", "skipped", "neutral", "unknown")}
    for check in checks:
        counts[_category(check)] += 1
    outputs.update(
        complete=complete, statuses_complete=statuses_complete, check_runs_complete=runs_complete,
        overall_state=_overall_state(checks, counts, complete=complete),
        total_count=len(checks), checks=checks,
        **{f"{name}_count": count for name, count in counts.items()},
    )
    return ok(summary="GitHub pull request checks retrieved successfully", outputs=outputs, raw=raw)


def _fetch_pages(ctx, *, identity, commit_sha, kind):
    """Follow all Link pages via gh, then verify advertised totals and identities.

    The combined status endpoint supplies the latest status per context. Check
    runs use GitHub's latest filter. Neither API is an atomic snapshot across pages.
    """
    suffix = "status" if kind == "statuses" else "check-runs"
    query = "per_page=100" if kind == "statuses" else "per_page=100&filter=latest"
    try:
        command = ctx.command(
            ["gh", "api", f"repos/{identity.owner}/{identity.repo}/commits/{commit_sha}/{suffix}?{query}",
             "--paginate", "--slurp"],
            failures={"os_error": "probe_failed"},
        )
    except MappedOutcomeError as exc:
        return fail_github_command(
            ctx, code="checks_unavailable", summary="GitHub pull request checks were unavailable",
            raw=exc.outcome.raw, diagnostic_code=f"probe.gh_pr_checks.{kind}_failed",
            details={"pull_ref": identity.pull_ref}, message="GitHub pull request checks were unavailable",
        )
    try:
        pages = json.loads(command.stdout)
        if not isinstance(pages, list) or not pages:
            raise ValueError("Expected a nonempty slurped list of API pages")
        for page in pages:
            if not isinstance(page, dict) or not isinstance(page.get(kind), list):
                raise ValueError(f"Expected a {kind} array in each page")
            if not all(isinstance(item, dict) for item in page[kind]):
                raise ValueError("Expected check objects")
            if page.get("sha") is not None and not isinstance(page["sha"], str):
                raise ValueError("Expected a string response SHA")
            for item in page[kind]:
                for field in ("status", "state", "conclusion", "head_sha"):
                    if item.get(field) is not None and not isinstance(item[field], str):
                        raise ValueError(f"Expected a string {field}")
    except (ValueError, TypeError) as exc:
        return _unavailable(ctx, f"{kind}_invalid_json", str(exc), raw=command.raw)
    if kind == "statuses" and any(page.get("sha") is not None and page["sha"] != commit_sha for page in pages):
        return _unavailable(ctx, "status_sha_mismatch", "GitHub status response belongs to a different commit", raw=command.raw)
    total = sum(len(page[kind]) for page in pages)
    complete = all(type(page.get("total_count")) is int and page["total_count"] == total for page in pages)
    # Duplicates indicate pagination drift. Do not silently deduplicate evidence.
    ids = [item.get("id") for page in pages for item in page[kind]]
    if any(type(value) is not int for value in ids) or len(set(ids)) != len(ids):
        complete = False
    if kind == "statuses":
        contexts = [item.get("context") for page in pages for item in page[kind]]
        if any(not isinstance(value, str) for value in contexts):
            complete = False
        elif len(set(contexts)) != len(contexts):
            complete = False
    return pages, command.raw, complete


def _normalize_statuses(payload):
    return [{
        "name": status.get("context") or status.get("description") or "status",
        "kind": "status", "state": status.get("state"),
        "status": "pending" if status.get("state") == "pending" else (
            "completed" if status.get("state") in ("success", "failure", "error") else None),
        "conclusion": None if status.get("state") == "pending" else status.get("state"),
        "context": status.get("context"), "url": status.get("target_url"),
        "sha": payload.get("sha"), "sha_source": "combined_status.sha",
        "id": status.get("id"), "created_at": status.get("created_at"),
        "updated_at": status.get("updated_at"), "started_at": None, "completed_at": None,
        "app_id": None, "app_slug": None, "app_identity": "unavailable",
        "creator": status.get("creator") if isinstance(status.get("creator"), dict) else None,
    } for status in payload["statuses"]]


def _normalize_check_runs(payload):
    items = []
    for run in payload["check_runs"]:
        app = run.get("app") if isinstance(run.get("app"), dict) else {}
        items.append({
            "name": run.get("name"), "kind": "check_run", "state": None,
            "status": run.get("status"), "conclusion": run.get("conclusion"),
            "context": None, "url": run.get("html_url") or run.get("details_url"),
            "sha": run.get("head_sha"), "sha_source": "check_run.head_sha",
            "id": run.get("id"), "created_at": run.get("created_at"),
            "updated_at": run.get("updated_at"), "started_at": run.get("started_at"),
            "completed_at": run.get("completed_at"), "app_id": app.get("id"),
            "app_slug": app.get("slug"), "creator": None,
            "app_identity": "available" if app.get("id") is not None and app.get("slug") is not None else "unavailable",
        })
    return items


def _category(check):
    status, conclusion = check["status"], check["conclusion"]
    if status in _PENDING_STATUSES and conclusion is None:
        return "pending"
    if status != "completed":
        return "unknown"
    if conclusion in _FAILED_CONCLUSIONS:
        return "failed"
    if conclusion in ("skipped", "neutral"):
        return conclusion
    if conclusion == "success" and check["sha"] is not None:
        return "success"
    return "unknown"


def _overall_state(checks, counts, *, complete):
    if not complete:
        return "incomplete"
    if not checks:
        return "no_checks"
    for name in ("failed", "pending", "unknown"):
        if counts[name]:
            return name
    if counts["success"] == len(checks):
        return "success"
    for name in ("skipped", "neutral"):
        if counts[name] == len(checks):
            return name
    return "mixed"
