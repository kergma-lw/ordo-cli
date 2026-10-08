"""Find Actions runs by GitHub filters and an explicit run-name correlation token."""

from __future__ import annotations

from urllib.parse import urlencode
import re

from connectors.gh._actions_run import ActionsObservation, object_value, pagination_links, positive_int, repository_matches, text
from ordo.model.human import declare_human
from ordo.plugin_sdk import MappedOutcomeError, OperationOutcome, probe


OUTPUTS = {"repository": "string", "workflow": "string", "event": "string", "ref": "string", "request_id": "string", "items": [{"run_id": "integer", "run_attempt": "integer", "run_name": "string", "event": "string", "ref": "string", "status": "string", "conclusion": "string", "url": "string"}], "count": "integer", "complete": "boolean"}
_WORKFLOW = re.compile(r"(?:[1-9][0-9]*|[A-Za-z0-9][A-Za-z0-9._-]*\.ya?ml)")

HUMAN = declare_human({"title": "GitHub actions run search", "goal": "Find every visible run of one workflow that carries a known correlation value in its run name.", "summary": "Search one workflow's runs with exact GitHub event, ref, and run-name correlation.", "sections": [
 {"heading": "Use when", "items": ["A manually dispatched workflow sets its complete run name to the supplied request ID and the workflow needs to observe all matching runs.", "Zero and multiple matches remain explicit results; this probe does not select one run."]},
 {"heading": "What to provide", "items": ["`repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide another OWNER/REPO to override that target.", "`workflow`: required; provide the GitHub workflow ID or file name.", "`event`: required; provide the GitHub event name.", "`ref`: required; provide the GitHub ref value without local normalization.", "`request_id`: required; provide the literal correlation value included in the workflow run name."]},
 {"heading": "Result and boundary", "items": ["The result includes `repository`, `workflow`, `event`, `ref`, `request_id`, `items`, `count`, and `complete`. `count=0` and `count>1` are successful results, not failures.", "`complete=true` means every accessible result page was read. Unavailable or incomplete listing has no usable result; a later GitHub change can alter the collection."]},
 {"heading": "Do not use for", "items": ["Choosing one run from several matches, waiting for a run, or deciding whether a run passed.", "Finding a workflow whose complete run name is not request_id."]},
 {"heading": "Related references", "body": "Use these related references to submit a correlated request or inspect one chosen run.", "references": [{"handle": "connector.gh.actions.dispatch", "summary": "Submit a manually dispatched workflow."}, {"handle": "connector.gh.actions.run", "summary": "Observe one selected Actions run."}]},
]})


def info():
    return probe(name="actions.run.search", human=HUMAN, summary="Find all correlated GitHub Actions runs without selecting one.", inputs={"repository": "string", "workflow": "string", "event": "string", "ref": "string", "request_id": "string"}, outputs=OUTPUTS, failure_modes=("input_error", "actions_run_search_unavailable"), handler=run)


def run(ctx):
    observation = ActionsObservation(ctx)
    observation.code, observation.prefix = "actions_run_search_unavailable", "probe.gh_actions_run_search"
    try:
        target = observation.repository()
        workflow, event, ref, request_id = (ctx.input(key) for key in ("workflow", "event", "ref", "request_id"))
        if not all(isinstance(value, str) and value and not any(ord(char) < 32 for char in value) for value in (workflow, event, ref, request_id)) or _WORKFLOW.fullmatch(workflow) is None:
            return observation.failure("invalid_input", "workflow, event, ref, and request_id must be nonblank strings without control characters", code="input_error")
        path = f"/repos/{target.repository}/actions/workflows/{workflow}/runs"
        items, page, total = [], 1, None
        while True:
            payload, headers = observation.request(f"{path[1:]}?{urlencode({'branch': ref, 'event': event, 'per_page': 100, 'page': page})}", include=True)
            current_total = positive_int(payload.get("total_count"), "total_count") if payload.get("total_count") else 0
            runs = payload.get("workflow_runs")
            if not isinstance(runs, list) or total is not None and total != current_total:
                raise ValueError("workflow runs response is incomplete or contradictory")
            total = current_total
            expected_count = min(100, total - (page - 1) * 100)
            if len(runs) != expected_count:
                raise ValueError("workflow run page is incomplete or contradicts total_count")
            for value in runs:
                value = object_value(value, "workflow run")
                repository_matches(object_value(value.get("repository"), "repository").get("full_name"), target.repository)
                if value.get("event") != event or value.get("head_branch") != ref:
                    raise ValueError("workflow run differs from requested GitHub filters")
                name = text(value.get("display_title"), "display_title", required=True)
                if request_id == name:
                    items.append({"run_id": positive_int(value.get("id"), "run id"), "run_attempt": positive_int(value.get("run_attempt"), "run_attempt"), "run_name": name, "event": event, "ref": ref, "status": text(value.get("status"), "status"), "conclusion": text(value.get("conclusion"), "conclusion"), "url": text(value.get("html_url"), "html_url", required=True)})
            last = max(1, (total + 99) // 100)
            pagination_links(headers, path=path, page=page, last_page=last, filters={"branch": ref, "event": event})
            if page >= last:
                break
            page += 1
            if page > 10:
                raise ValueError("workflow run listing exceeded GitHub's searchable result window")
        return observation.success("Correlated GitHub Actions runs observed", {"repository": target.repository, "workflow": workflow, "event": event, "ref": ref, "request_id": request_id, "items": items, "count": len(items), "complete": True}, target)
    except MappedOutcomeError as exc:
        return exc.outcome
    except (ValueError, TypeError) as exc:
        return observation.failure("invalid_response", str(exc))
