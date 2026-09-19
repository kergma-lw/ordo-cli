"""Observe one exact Actions run attempt without applying acceptance policy."""

from connectors.gh._actions_run import (
    ActionsObservation, object_value, positive_int, repository_matches, text, validate_run,
)
from ordo.plugin_sdk import MappedOutcomeError, probe

OUTPUTS = {
    "repository": "string", "found": "boolean", "run_id": "integer",
    "check_suite_id": "integer", "run_attempt": "integer", "workflow_id": "integer",
    "workflow_path": "string", "event": "string", "status": "string", "conclusion": "string",
    "head_sha": "string", "head_branch": "string", "url": "string", "created_at": "string",
    "updated_at": "string", "run_started_at": "string",
    "pull_requests": [{"number": "integer", "head_sha": "string", "base_sha": "string"}],
}
QUERY = (
    "query($id:ID!){node(id:$id){__typename ... on CheckSuite{"
    "id repository{nameWithOwner} workflowRun{__typename databaseId checkSuite{id}}}}}"
)


def info():
    return probe(
        name="actions.run",
        summary="Observe an exact Actions attempt by run or check suite; omitted attempt pins the latest observed attempt. PR SHAs are API observations, not immutable event snapshots.",
        inputs={"repository": "string", "run_id": "integer", "check_suite_id": "integer", "attempt": "integer"},
        outputs=OUTPUTS, failure_modes=("input_error", "actions_run_unavailable"), handler=run,
    )


def _suite_run(observation, repository, suite_id):
    suite = observation.request(f"repos/{repository}/check-suites/{suite_id}")
    if positive_int(suite.get("id"), "check suite id") != suite_id:
        raise ValueError("API check suite id does not match the requested suite")
    node_id = text(suite.get("node_id"), "check suite node_id", required=True)
    payload = observation.request("graphql", fields=["-f", f"query={QUERY}", "-f", f"id={node_id}"])
    if "errors" in payload and payload["errors"] != []:
        raise ValueError("GraphQL returned errors or a malformed errors field")
    node = object_value(object_value(payload.get("data"), "GraphQL data").get("node"), "CheckSuite node")
    if node.get("__typename") != "CheckSuite" or node.get("id") != node_id:
        raise ValueError("GraphQL returned a different check suite node")
    repository_matches(object_value(node.get("repository"), "CheckSuite repository").get("nameWithOwner"), repository)
    if "workflowRun" not in node:
        raise ValueError("GraphQL omitted the workflowRun association")
    if node["workflowRun"] is None:
        return None, node_id
    workflow_run = object_value(node["workflowRun"], "workflowRun")
    if workflow_run.get("__typename") != "WorkflowRun":
        raise ValueError("GraphQL returned an unexpected workflowRun type")
    if object_value(workflow_run.get("checkSuite"), "workflowRun checkSuite").get("id") != node_id:
        raise ValueError("GraphQL workflowRun check suite backreference differs")
    return positive_int(workflow_run.get("databaseId"), "workflowRun databaseId"), node_id


def _outputs(payload, repository):
    outputs = {key: None for key in OUTPUTS}
    outputs.update(repository=repository, found=True, run_id=payload["id"],
                   check_suite_id=payload["check_suite_id"], run_attempt=payload["run_attempt"])
    if payload.get("workflow_id") is not None:
        outputs["workflow_id"] = positive_int(payload["workflow_id"], "workflow_id")
    for field in ("workflow_path", "event", "status", "conclusion", "head_sha", "head_branch",
                  "url", "created_at", "updated_at", "run_started_at"):
        source = {"workflow_path": "path", "url": "html_url"}.get(field, field)
        outputs[field] = text(payload.get(source), source, sha=field == "head_sha")
    pulls = payload.get("pull_requests", [])
    if not isinstance(pulls, list):
        raise ValueError("pull_requests must be an array")
    outputs["pull_requests"] = []
    for pull in pulls:
        pull = object_value(pull, "pull request")
        item = {"number": positive_int(pull.get("number"), "pull request number")}
        for side in ("head", "base"):
            value = pull.get(side)
            item[f"{side}_sha"] = None if value is None else text(
                object_value(value, side).get("sha"), f"{side} SHA", sha=True)
        outputs["pull_requests"].append(item)
    return outputs


def run(ctx):
    observation = ActionsObservation(ctx)
    try:
        target = observation.repository()
        run_id, suite_id, attempt = (ctx.optional_input(key) for key in ("run_id", "check_suite_id", "attempt"))
        try:
            if (run_id is None) == (suite_id is None):
                raise ValueError("Exactly one of run_id and check_suite_id is required")
            for field, value in (("run_id", run_id), ("check_suite_id", suite_id), ("attempt", attempt)):
                if value is not None:
                    positive_int(value, field)
        except ValueError as exc:
            return observation.failure("invalid_input", str(exc), code="input_error")
        repository = target.repository
        suite_node = None
        if suite_id is not None:
            run_id, suite_node = _suite_run(observation, repository, suite_id)
            if run_id is None:
                outputs = {key: None for key in OUTPUTS}
                outputs.update(repository=repository, found=False, check_suite_id=suite_id, pull_requests=[])
                return observation.success("Check suite has no associated Actions run", outputs, target)
        endpoint = f"repos/{repository}/actions/runs/{run_id}"
        if attempt is None:
            latest = observation.request(endpoint)
            attempt, suite_id = validate_run(latest, repository=repository, run_id=run_id,
                                            suite_id=suite_id, suite_node=suite_node)
        payload = observation.request(f"{endpoint}/attempts/{attempt}")
        validate_run(payload, repository=repository, run_id=run_id, attempt=attempt,
                     suite_id=suite_id, suite_node=suite_node)
        return observation.success("GitHub Actions run attempt observed", _outputs(payload, repository), target)
    except MappedOutcomeError as exc:
        return exc.outcome
    except (ValueError, TypeError) as exc:
        return observation.failure("invalid_response", str(exc))
