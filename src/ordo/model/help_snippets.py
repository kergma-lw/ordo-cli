"""Canonical help snippets and snippet-coverage metadata."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from .json import JSONObject


_REPO_ROOT = Path(__file__).resolve().parents[3]


HELP_SNIPPET_REGISTRY: dict[str, JSONObject] = {
    "state": {
        "snippet_coverage": "harness_verified",
        "canonical_examples": [
            {
                "name": "fixed_shared_state_key",
                "kind": "positive",
                "summary": "Read one fixed shared-state key directly with a literal key selector.",
                "yaml": 'state.shared_state["active_profile"]',
                "verification": {
                    "kind": "harness_verified",
                    "harness": "state_expression_in_let",
                    "expected_status": "ok",
                },
            },
            {
                "name": "dynamic_shared_state_key",
                "kind": "positive",
                "summary": "Read one shared-state value through a dynamic key from inputs.",
                "yaml": "state.shared_state[inputs.active_profile_key]",
                "verification": {
                    "kind": "harness_verified",
                    "harness": "state_expression_in_let",
                    "expected_status": "ok",
                },
            },
        ],
    },
    "workflow.step.if": {
        "snippet_coverage": "harness_verified",
        "canonical_examples": [
            {
                "name": "step_if_reads_state_directly",
                "kind": "positive",
                "summary": "Gate one step with a direct fixed-key state read.",
                "yaml": 'state.shared_state["active_profile"] == "review"',
                "verification": {
                    "kind": "harness_verified",
                    "harness": "step_if_expression",
                    "expected_status": "ok",
                },
            }
        ],
    },
    "workflow.step.state_set": {
        "snippet_coverage": "harness_verified",
        "canonical_examples": [
            {
                "name": "state_set_fixed_shared_state_key",
                "kind": "positive",
                "summary": "Write one value to a fixed shared-state key directly with a literal key selector.",
                "yaml": 'state_set:\n  state.shared_state["active_profile"]: review',
                "verification": {
                    "kind": "harness_verified",
                    "harness": "step_state_set_mapping",
                    "expected_status": "ok",
                },
            },
            {
                "name": "state_set_fixed_shared_state_nested_field",
                "kind": "positive",
                "summary": "Write one nested field under a fixed shared-state key.",
                "yaml": 'state_set:\n  state.shared_state["active_profile"].enabled: true',
                "verification": {
                    "kind": "harness_verified",
                    "harness": "step_state_set_mapping",
                    "expected_status": "ok",
                },
            },
            {
                "name": "state_set_dynamic_task_memory_key",
                "kind": "positive",
                "summary": "Persist one value under a state path whose key comes from inputs.",
                "source_example": "examples.set-active-task-from-gitx",
                "source_excerpt": {
                    "path": "examples/set-active-task-from-gitx.yaml",
                    "start_line": 105,
                    "end_line": 107,
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.set-active-task-from-gitx",
                },
            }
        ],
    },
    "workflow.local_expression.filter.lookup": {
        "snippet_coverage": "harness_verified",
        "canonical_examples": [
            {
                "name": "lookup_fixed_mapping_key",
                "kind": "positive",
                "summary": "Select one mapping value with the lookup pipeline filter.",
                "yaml": 'inputs.status_labels | lookup("ready")',
                "verification": {
                    "kind": "harness_verified",
                    "harness": "value_expression_lookup",
                    "expected_status": "ok",
                },
            }
        ],
    },
}


def _load_excerpt_text(*, path: str, start_line: int, end_line: int) -> str:
    lines = (_REPO_ROOT / path).read_text(encoding="utf-8").splitlines()
    excerpt = lines[start_line - 1 : end_line]
    return "\n".join(excerpt)


def describe_help_snippets() -> dict[str, JSONObject]:
    """Return published help-snippet metadata with rendered excerpt bodies."""

    payload: dict[str, JSONObject] = deepcopy(HELP_SNIPPET_REGISTRY)
    for entry in payload.values():
        for example in entry.get("canonical_examples", []):
            if not isinstance(example, dict):
                continue
            excerpt = example.get("source_excerpt")
            if isinstance(excerpt, dict):
                example["yaml"] = _load_excerpt_text(
                    path=str(excerpt["path"]),
                    start_line=int(excerpt["start_line"]),
                    end_line=int(excerpt["end_line"]),
                )
    return payload
