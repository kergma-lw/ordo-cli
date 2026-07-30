"""gh.pr.timeline probe."""

from __future__ import annotations

from connectors.gh._pull_identity import PULL_IDENTITY_INPUTS, resolve_pull_identity
from connectors.gh.probes.pr._shared import fetch_json_list, fetch_pull_request, normalize_author, resolve_limit
from ordo.plugin_sdk import OperationContext, OperationOutcome, ok, probe

_SUPPORTED_EVENTS = {
    "ready_for_review",
    "converted_to_draft",
    "review_requested",
    "review_request_removed",
    "head_ref_force_pushed",
    "base_ref_changed",
    "labeled",
    "unlabeled",
    "merged",
    "closed",
    "reopened",
}


def info():
    return probe(
        name="pr.timeline",
        summary="Read normalized lifecycle events from a GitHub pull request timeline.",
        inputs={**PULL_IDENTITY_INPUTS, "limit": "integer"},
        outputs={"pull_ref": "string", "total_count": "integer", "events": ["object"]},
        failure_modes=("pull_not_found", "limit_invalid", "probe_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    identity = resolve_pull_identity(ctx, failure_code="probe_failed", diagnostic_prefix="probe.gh_pr.timeline")
    if isinstance(identity, OperationOutcome):
        return identity
    limit = resolve_limit(
        ctx,
        pull_ref=identity.pull_ref,
        diagnostic_prefix="probe.gh_pr.timeline",
        summary_subject="GitHub pull request timeline",
    )
    if isinstance(limit, OperationOutcome):
        return limit
    fetched_pull = fetch_pull_request(ctx, identity=identity, diagnostic_prefix="probe.gh_pr.timeline")
    if isinstance(fetched_pull, OperationOutcome):
        return fetched_pull
    pull_payload, pull_raw = fetched_pull
    fetched_events = fetch_json_list(
        ctx,
        argv=["gh", "api", f"repos/{identity.owner}/{identity.repo}/issues/{identity.pull_number}/timeline?per_page={limit}"],
        diagnostic_prefix="probe.gh_pr.timeline",
        pull_ref=identity.pull_ref,
        failed_summary="GitHub pull request timeline probe failed",
    )
    if isinstance(fetched_events, OperationOutcome):
        return fetched_events
    payload, events_raw = fetched_events
    events = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_event(item)
        if normalized is not None:
            events.append(normalized)
    return ok(
        summary="GitHub pull request timeline retrieved successfully",
        outputs={"pull_ref": identity.pull_ref, "total_count": len(events), "events": events},
        raw={"pull": pull_raw, "timeline": events_raw, "pull_state": pull_payload.get("state")},
    )


def _normalize_event(item: dict[str, object]) -> dict[str, object] | None:
    event_type = item.get("event")
    if not isinstance(event_type, str) or event_type not in _SUPPORTED_EVENTS:
        return None
    payload: dict[str, object] = {}
    from_value = None
    to_value = None
    if event_type in {"labeled", "unlabeled"}:
        label = item.get("label")
        if isinstance(label, dict):
            payload["label"] = label.get("name")
    elif event_type in {"review_requested", "review_request_removed"}:
        requested_reviewer = item.get("requested_reviewer")
        requested_team = item.get("requested_team")
        if isinstance(requested_reviewer, dict):
            payload["requested_reviewer"] = requested_reviewer.get("login")
        if isinstance(requested_team, dict):
            payload["requested_team"] = requested_team.get("name")
    elif event_type == "head_ref_force_pushed":
        payload["before_commit_id"] = item.get("before")
        payload["after_commit_id"] = item.get("after")
        payload["head_ref"] = item.get("ref")
    elif event_type == "base_ref_changed":
        from_value = item.get("previous_ref")
        to_value = item.get("current_ref")
    elif event_type == "merged":
        payload["commit_id"] = item.get("commit_id")
    created_at = item.get("created_at")
    if created_at is None:
        created_at = item.get("submitted_at")
    return {
        "event_type": event_type,
        "actor": normalize_author(item.get("actor")),
        "created_at": created_at,
        "from_value": from_value,
        "to_value": to_value,
        "payload": payload,
    }
