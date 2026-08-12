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
class SnippetWorld:
    """Named teaching-world fixture data for help snippets."""

    name: str
    summary: str
    inputs: JSONObject
    state: JSONObject
    probes: dict[str, list[ProbeFixture]]
    actions: dict[str, ActionFixture]


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


def describe_help_snippet_worlds() -> dict[str, JSONObject]:
    """Return published snippet-world fixture data in machine-readable form."""

    payload = {name: _world_to_json(world) for name, world in SNIPPET_WORLDS.items()}
    _validate_world_payload(payload)
    return payload


def _world_to_json(world: SnippetWorld) -> JSONObject:
    data = asdict(world)
    return deepcopy(data)


def _validate_world_payload(worlds: dict[str, JSONObject]) -> None:
    for world_name, world in worlds.items():
        if set(world.keys()) != {"name", "summary", "inputs", "state", "probes", "actions"}:
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
