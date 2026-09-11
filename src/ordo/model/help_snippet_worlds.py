"""Named fixture worlds for help-snippet verification and publication."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass

from .json import JSONValue, JSONObject


@dataclass(frozen=True)
class ProbeFixture:
    """One declared probe result in a snippet world."""

    with_: JSONObject
    outputs: JSONObject


@dataclass(frozen=True)
class ActionFixture:
    """One declared action outcome in a snippet world."""

    status: str
    outputs: JSONObject


@dataclass(frozen=True)
class ResolvedActionFixture(ActionFixture):
    """Execution fixtures must match the entire materialized action input map."""

    with_: JSONObject


@dataclass(frozen=True)
class SnippetWorld:
    """Named teaching-world fixture data for help snippets."""

    name: str
    summary: str
    inputs: JSONObject
    state: JSONObject
    probes: dict[str, list[ProbeFixture]]
    actions: dict[str, ActionFixture]
    connector_contexts: JSONObject | None = None


DEFAULT_SNIPPET_WORLD = SnippetWorld(
    name="default",
    summary="Stable teaching world for help examples.",
    inputs={
        "repository": "acme/mobile-app",
        "issue_number": 42,
        "project_id": "PVT_demo",
        "close_comment": "Ship it",
        "task_key": "task-42",
        "ship": True,
    },
    state={
        "shared_state": {
            "active_profile": "review",
            "should_publish_summary": True,
        },
        "common_state": {
            "acme/mobile-app": {
                "issue_number": 42,
                "branch": "task/42-close-issue",
            }
        },
        "task_memory": {
            "task-42": {
                "issue_number": 42,
            }
        },
    },
    probes={
        "git.repo": [ProbeFixture(with_={}, outputs={"exists": True})],
        "git.branch": [ProbeFixture(with_={}, outputs={"value": "task/42-close-issue"})],
        "git.worktree": [ProbeFixture(with_={}, outputs={"clean": True})],
        "gh.issue": [
            ProbeFixture(
                with_={
                    "repository": {"expression": "inputs.repository"},
                    "issue_number": {"expression": "inputs.issue_number"},
                },
                outputs={"state": "OPEN"},
            ),
        ],
        "gh.project.issue": [
            ProbeFixture(
                with_={
                    "repository": {"expression": "inputs.repository"},
                    "issue_number": {"expression": "inputs.issue_number"},
                    "project_id": {"expression": "inputs.project_id"},
                },
                outputs={"exists": True, "status": "In review"},
            ),
        ],
        "gh.project.field": [
            ProbeFixture(
                with_={
                    "project_id": {"expression": "inputs.project_id"},
                    "field": "Status",
                },
                outputs={"exists": True},
            ),
        ],
        "gh.project.field.option": [
            ProbeFixture(
                with_={
                    "project_id": {"expression": "inputs.project_id"},
                    "field": "Status",
                    "option": "Done",
                },
                outputs={"exists": True},
            ),
        ],
    },
    actions={
        "gh.issue.comment.add": ActionFixture(status="ok", outputs={}),
        "gh.project.issue.field_single_select.set": ActionFixture(status="ok", outputs={}),
    },
)


SNIPPET_WORLDS: dict[str, SnippetWorld] = {
    DEFAULT_SNIPPET_WORLD.name: DEFAULT_SNIPPET_WORLD,
}


def _merge_world(*, test_merge: bool, context_repository: bool = False) -> SnippetWorld:
    head, base, candidate = "a" * 40, "b" * 40, "c" * 40
    request_id = "12345678-1234-1234-1234-123456789abc"
    identity = {"repository": "acme/mobile-app", "pull_number": 42}
    merge_identity = {"pull_number": 42} if context_repository else identity
    target = "test_merge" if test_merge else "head"
    pr = {"head_sha": head, "base_sha": base, "state": "open", "draft": False,
          "stack_state": "standalone", "merged": False, "merge_commit_sha": None,
          "mergeable": True, "mergeable_state": "clean", "test_merge_state": "verified",
          "test_merge_sha": candidate, "test_merge_head_sha": head, "test_merge_base_sha": base}
    checks = {"head_sha": head, "base_sha": base, "expected_head_sha": head,
              "target": target, "commit_sha": candidate if test_merge else head,
              "complete": True, "statuses_complete": True, "check_runs_complete": True,
              "overall_state": "success", "test_merge_state": "verified" if test_merge else "not_requested",
              "test_merge_sha": candidate if test_merge else None,
              "test_merge_head_sha": head if test_merge else None,
              "test_merge_base_sha": base if test_merge else None,
              "checks": [{"name": "unit", "kind": "check_run", "app_id": 15368,
                          "app_slug": "github-actions", "status": "completed", "conclusion": "success",
                          "sha": candidate if test_merge else head}]}
    submission = {**identity, "request_id": request_id, "state": "pending", "merged": False,
                  "merge_sha": None, "merge_method": "squash", "merge_action": "direct_merge",
                  "expected_head_sha": head, "submission": "accepted", "request_compatibility": "exact",
                  "http_status": 202, "message": "Merge pending"}
    return SnippetWorld(
        name=("gh-pr-merge-test-merge" if test_merge else "gh-pr-merge-head") + ("-context" if context_repository else ""),
        summary="Fixture-only execution: PR before/after submission, pinned checks, strict action inputs, saved UUID observation.",
        inputs={**identity, "authorize_merge": True}, state={},
        connector_contexts={"gh": {"repository": identity["repository"]}} if context_repository else None,
        probes={
            "gh.pr": [ProbeFixture(with_=identity, outputs=pr),
                      ProbeFixture(with_=identity, outputs={**pr, "state": "closed", "merged": True,
                                                           "merge_commit_sha": "d" * 40})],
            "gh.pr.checks": [ProbeFixture(with_={**identity, "target": target, "expected_head_sha": head}, outputs=checks)],
            "gh.pr.merge.request": [ProbeFixture(with_={**merge_identity, "request_id": request_id},
                                                 outputs={**submission, "state": "merged", "merged": True,
                                                          "http_status": 200, "merge_sha": "d" * 40,
                                                          "message": "Merged"})],
        },
        actions={"gh.pr.merge": ResolvedActionFixture(
            status="ok", outputs=submission,
            with_={**merge_identity, "merge_method": "squash", "expected_head_sha": head})},
    )


for _test_merge, _context_repository in ((False, False), (True, False), (False, True)):
    _world = _merge_world(test_merge=_test_merge, context_repository=_context_repository)
    SNIPPET_WORLDS[_world.name] = _world


def _pr_list_world(case: str) -> SnippetWorld:
    repository, head_repository = "acme/mobile-app", "contributor/mobile-app"
    inputs = {"repository": repository, "head": "task/42", "head_owner": "contributor",
              "base": "main", "head_repository": head_repository}
    filters = {key: value for key, value in inputs.items() if key != "head_repository"}
    filters["state"] = "all"

    def item(number: int, *, closed: bool = False, merged: bool | None = False) -> JSONObject:
        return {"number": number, "url": f"https://github.com/{repository}/pull/{number}",
                "state": "closed" if closed else "open", "draft": False, "merged": merged,
                "merged_at": "2026-09-01T12:00:00Z" if merged else None,
                "head_repository": head_repository, "head_owner": "contributor", "head_ref": "task/42",
                "head_repository_key": head_repository.lower(),
                "head_sha": "a" * 40, "base_repository": repository, "base_ref": "main",
                "base_sha": "b" * 40, "pull_ref": f"{repository}#{number}"}

    items = {
        "no-pr": [],
        "exactly-one-open": [item(42), {**item(43), "head_repository": "contributor/other-fork",
                                      "head_repository_key": "contributor/other-fork"}],
        "ambiguous-multiple-open": [item(42), item(43)],
        "only-closed-history": [item(40, closed=True), item(41, closed=True, merged=True)],
        "unknown-metadata": [{**item(42, merged=None), "head_repository": None, "head_repository_key": None}],
    }[case]
    return SnippetWorld(
        name=f"gh-pr-list-{case}", summary="Fixture-only complete PR candidate observation and workflow-owned classification.",
        inputs=inputs, state={}, actions={},
        probes={"gh.pr.list": [ProbeFixture(with_=filters, outputs={
            **filters, "items": items, "count": len(items), "complete": True,
        })]},
    )


for _case in ("no-pr", "exactly-one-open", "ambiguous-multiple-open", "only-closed-history", "unknown-metadata"):
    _world = _pr_list_world(_case)
    SNIPPET_WORLDS[_world.name] = _world


def _pr_create_world() -> SnippetWorld:
    observation = _pr_list_world("no-pr")
    inputs = {**observation.inputs, "head_repository_name": "mobile-app",
              "title": "Ship task 42", "body": "Implementation and verification details.",
              "draft": True, "authorize_create": True}
    identity = {"repository": inputs["repository"], "pull_number": 73}
    created = {**identity, "pull_ref": "acme/mobile-app#73",
               "url": "https://github.com/acme/mobile-app/pull/73", "created": True,
               "head_repository": inputs["head_repository"], "head_owner": inputs["head_owner"],
               "head_ref": inputs["head"], "head_sha": "a" * 40,
               "base_repository": inputs["repository"], "base_ref": inputs["base"], "base_sha": "b" * 40}
    return SnippetWorld(
        name="gh-pr-create-new-only",
        summary="Create-only workflow policy and saved-number observation using strict fixtures, not internal SDK or HTTP execution.",
        inputs=inputs, state={},
        probes={**observation.probes, "gh.pr": [ProbeFixture(with_=identity, outputs={"state": "open"})]},
        actions={"gh.pr.create": ResolvedActionFixture(
            status="ok", outputs=created,
            with_={key: inputs[key] for key in ("repository", "head", "head_owner", "head_repository", "base", "title", "body", "draft")})},
    )


_world = _pr_create_world()
SNIPPET_WORLDS[_world.name] = _world


def _sdk_probe_world() -> SnippetWorld:
    observation = _pr_list_world("exactly-one-open")
    filters = deepcopy(observation.probes["gh.pr.list"][0].with_)
    return SnippetWorld(
        name="gh-sdk-probe-call",
        summary="Real same-family SDK dispatch and isolated literal inputs; bootstrap and PR-list body are fixtures.",
        inputs={"filters": filters}, state={}, probes=observation.probes, actions={},
    )


_world = _sdk_probe_world()
SNIPPET_WORLDS[_world.name] = _world


def describe_help_snippet_worlds() -> dict[str, JSONObject]:
    """Return published snippet-world fixture data in machine-readable form."""

    payload = {name: _world_to_json(world) for name, world in SNIPPET_WORLDS.items()}
    _validate_world_payload(payload)
    return payload


def _world_to_json(world: SnippetWorld) -> JSONObject:
    data = asdict(world)
    if data["connector_contexts"] is None:
        del data["connector_contexts"]
    return deepcopy(data)


def _validate_world_payload(worlds: dict[str, JSONObject]) -> None:
    for world_name, world in worlds.items():
        if set(world.keys()) - {"connector_contexts"} != {"name", "summary", "inputs", "state", "probes", "actions"}:
            raise ValueError(f"Unsupported snippet world shape for {world_name}")
        _validate_json_value(world)


def _validate_json_value(value: JSONValue | dict[str, object]) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, list):
        for item in value:
            _validate_json_value(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("Snippet world payload keys must be strings")
            _validate_json_value(item)
        return
    raise ValueError(f"Unsupported snippet world payload value: {value!r}")
