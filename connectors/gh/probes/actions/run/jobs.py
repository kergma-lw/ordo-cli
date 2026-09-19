"""Observe all jobs attached to a requested Actions run attempt."""

import re

from connectors.gh._actions_run import (
    ActionsObservation, api_url, object_value, pagination_links, positive_int, text,
)
from ordo.plugin_sdk import MappedOutcomeError, probe

MAX_PAGES = 100
ITEM_OUTPUTS = {
    "job_id": "integer", "name": "string", "status": "string", "conclusion": "string",
    "head_sha": "string", "check_run_id": "integer", "url": "string",
    "started_at": "string", "completed_at": "string",
}


def info():
    return probe(
        name="actions.run.jobs", summary="Observe all jobs for an exact Actions run attempt; fail on incomplete or inconsistent pagination.",
        inputs={"repository": "string", "run_id": "integer", "attempt": "integer"},
        outputs={"repository": "string", "run_id": "integer", "run_attempt": "integer",
                 "items": [ITEM_OUTPUTS], "count": "integer", "complete": "boolean"},
        failure_modes=("input_error", "actions_jobs_unavailable"), handler=run,
    )


def _job(payload, *, repository, run_id, attempt):
    payload = object_value(payload, "job")
    if positive_int(payload.get("run_id"), "job run_id") != run_id:
        raise ValueError("Job belongs to a different run")
    if positive_int(payload.get("run_attempt"), "job run_attempt") != attempt:
        raise ValueError("Job belongs to a different attempt")
    result = {"job_id": positive_int(payload.get("id"), "job id"), "check_run_id": None}
    for field in ("name", "status", "conclusion", "head_sha", "url", "started_at", "completed_at"):
        result[field] = text(payload.get("html_url" if field == "url" else field), field, sha=field == "head_sha")
    link = payload.get("check_run_url")
    if link is not None:
        text(link, "check_run_url", required=True)
        match = re.fullmatch(r"https://api\.github\.com/repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/check-runs/([1-9][0-9]*)", link)
        if match is None:
            raise ValueError("Malformed or mismatched check_run_url")
        check_id = int(match.group(1))
        api_url(link, f"/repos/{repository}/check-runs/{check_id}")
        result["check_run_id"] = check_id
    return result


def run(ctx):
    observation = ActionsObservation(ctx, jobs=True)
    try:
        target = observation.repository()
        try:
            run_id = positive_int(ctx.optional_input("run_id"), "run_id")
            attempt = positive_int(ctx.optional_input("attempt"), "attempt")
        except ValueError as exc:
            return observation.failure("invalid_input", str(exc), code="input_error")
        repository = target.repository
        path = f"/repos/{repository}/actions/runs/{run_id}/attempts/{attempt}/jobs"
        items, ids, total = [], set(), None
        for page in range(1, MAX_PAGES + 1):
            payload, links = observation.request(f"{path[1:]}?per_page=100&page={page}", include=True)
            advertised = payload.get("total_count")
            if type(advertised) is not int or advertised < 0:
                raise ValueError("Jobs total_count must be a nonnegative integer")
            if total is None:
                total = advertised
            if total != advertised:
                raise ValueError("Jobs total changed during pagination")
            last_page = max(1, (total + 99) // 100)
            if last_page > MAX_PAGES:
                raise ValueError("Jobs pagination exceeds the page limit")
            jobs = payload.get("jobs")
            expected_count = min(100, total - (page - 1) * 100)
            if not isinstance(jobs, list) or len(jobs) != expected_count:
                raise ValueError("Jobs page is incomplete or contradicts total_count")
            pagination_links(links, path=path, page=page, last_page=last_page)
            for job in jobs:
                item = _job(job, repository=repository, run_id=run_id, attempt=attempt)
                if item["job_id"] in ids:
                    raise ValueError("Duplicate job id during pagination")
                ids.add(item["job_id"])
                items.append(item)
            if page == last_page:
                return observation.success(
                    "GitHub Actions attempt jobs observed completely",
                    {"repository": repository, "run_id": run_id, "run_attempt": attempt,
                     "items": items, "count": len(items), "complete": True}, target,
                )
        raise ValueError("Jobs pagination exceeds the page limit")
    except MappedOutcomeError as exc:
        return exc.outcome
    except (ValueError, TypeError) as exc:
        return observation.failure("invalid_response", str(exc))
