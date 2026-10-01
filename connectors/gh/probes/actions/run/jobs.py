"""Observe all jobs attached to a requested Actions run attempt."""

import re

from connectors.gh._actions_run import (
    ActionsObservation, api_url, object_value, pagination_links, positive_int, text,
)
from ordo.plugin_sdk import MappedOutcomeError, probe
from ordo.model.human import declare_human

MAX_PAGES = 100
ITEM_OUTPUTS = {
    "job_id": "integer", "name": "string", "status": "string", "conclusion": "string",
    "head_sha": "string", "check_run_id": "integer", "url": "string",
    "started_at": "string", "completed_at": "string",
}


HUMAN = declare_human({'title': 'GitHub actions run jobs',
 'goal': 'Supply required positive integer run_id and explicit positive integer attempt, normally from gh.actions.run '
         'outputs run_id and run_attempt. There is no latest-attempt default or caller limit; booleans are invalid '
         'identifiers.',
 'summary': 'Observe the complete job collection for one explicitly numbered GitHub Actions run attempt.',
 'sections': [{'heading': 'Use when',
               'items': ['Supply required positive integer run_id and explicit positive integer attempt, normally from '
                         'gh.actions.run outputs run_id and run_attempt. There is no latest-attempt default or caller '
                         'limit; booleans are invalid identifiers.',
                          "Repository is optional and nullable. Leave it out to use the workflow's GitHub repository "
                          'context, or provide a valid ASCII OWNER/REPO value to inspect another repository. An invalid '
                          'explicit value is rejected rather than falling back to the workflow target. The selected '
                          'repository must be accessible to the authenticated GitHub command-line session.',
                         'Outputs are repository, run_id, run_attempt, items, count and complete=true. Each item '
                         'contains positive job_id, nullable check_run_id, and nullable '
                         'name/status/conclusion/head_sha/url/started_at/completed_at. Present head_sha is a full '
                         'hexadecimal SHA. Empty retrieval is items=[], count=0, complete=true, not successful CI.',
                          'check_run_id is retained only when the job has a repository-matching check association, '
                          'not from logs or display URLs. A missing link gives null identity; malformed or '
                         'mismatched links fail. Correlate this ID with gh.pr.checks check-run item id, whose '
                         'check_suite_id supplies the suite-to-run bridge.',
                         'Traverse attempt-scoped pages of 100 jobs, up to 100 pages, requiring stable total_count, '
                          'exact page sizes, valid page relations, unique job IDs and matching run/attempt '
                         'per job. count equals len(items). Incomplete or inconsistent traversal fails rather than '
                         'publishing partial success.',
                           'Invalid repository, run ID, or attempt values are rejected. The result is unavailable when '
                           'jobs cannot be read completely, do not belong to the selected run and attempt, have an '
                           'invalid check association, or change while pages are read. Partial job lists are never '
                          'returned as complete results.']},
               {'heading': 'What to provide',
                'items': ['Provide required positive integer `run_id` and `attempt`, normally from `gh.actions.run` results. There is no latest-attempt default.',
                          'Provide `repository` only to override the workflow GitHub repository context.']},
               {'heading': 'Result and boundary',
                'items': ['Later steps can use `repository`, `run_id`, `run_attempt`, `items`, `count`, and `complete`. Each job item supplies `job_id`, status and conclusion facts, `head_sha`, and `check_run_id` when known.',
                           '`complete=true` means the job collection was fully observed, including `items=[]` and `count=0`; it does not mean CI passed. Incomplete, contradictory, or unavailable pages fail instead of returning partial results. The collection is not an atomic snapshot.']},
               {'heading': 'Do not use for',
               'items': ['Selecting the latest attempt implicitly, triggering, rerunning, cancelling, polling, '
                         'downloading logs, choosing required jobs, or enforcing merge policy; this is read-only '
                         'observation.',
                          'Treating complete as an atomic snapshot, CI success, or immutable event-time data. '
                          'Cross-page and cross-probe observations are non-atomic.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.gh.actions.run',
                               'summary': 'Resolve a run or suite association and pin its observed run_attempt before '
                                          'reading jobs'},
                              {'handle': 'connector.gh.pr.checks',
                               'summary': 'PR-attached status/check evidence, not an Actions job collection'},
                               {'handle': 'connector.gh',
                                'summary': 'GitHub access requirements and family operation boundaries'}]},
              {'heading': 'Inspect next',
               'items': ['connector.gh.actions.run', 'connector.gh.pr.checks', 'connector.gh']}]})

def info():
    return probe(
        name="actions.run.jobs",
        human=HUMAN, summary="Observe all jobs for an exact Actions run attempt; fail on incomplete or inconsistent pagination.",
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
