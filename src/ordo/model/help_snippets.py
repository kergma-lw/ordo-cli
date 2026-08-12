"""Canonical help snippets and snippet-coverage metadata."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from .json import JSONObject


SUPPORTED_SNIPPET_FORMS = {
    "value",
    "field_fragment",
    "step_fragment",
    "workflow_fragment",
}

SUPPORTED_SNIPPET_VERIFICATION_KINDS = {
    "harness_verified",
    "excerpt_verified",
    "runner_verified",
}

SUPPORTED_SNIPPET_INSERTION_MODES = {
    "expression_value",
    "step_field",
    "step_fragment",
    "workflow_fragment",
}


_REPO_ROOT = Path(__file__).resolve().parents[3]


HELP_SNIPPET_REGISTRY: dict[str, JSONObject] = {
    "state": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "fixed_shared_state_key",
                "kind": "positive",
                "form": "value",
                "summary": "Read one fixed shared-state key directly with a literal key selector.",
                "yaml": 'state.shared_state["active_profile"]',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "expression_value",
                    "target": "state",
                    "expected_status": "ok",
                },
            },
            {
                "name": "dynamic_shared_state_key",
                "kind": "positive",
                "form": "value",
                "summary": "Read one shared-state value through a dynamic key from inputs.",
                "yaml": "state.shared_state[inputs.active_profile_key]",
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "expression_value",
                    "target": "state",
                    "expected_status": "ok",
                },
            },
        ],
    },
    "workflow.step.if": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "step_if_reads_state_directly",
                "kind": "positive",
                "form": "value",
                "summary": "Gate one step with a direct fixed-key state read.",
                "yaml": 'state.shared_state["active_profile"] == "review"',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_field",
                    "target": "workflow.step.if",
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
                "form": "field_fragment",
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
                "form": "field_fragment",
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
                "form": "field_fragment",
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
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "lookup_fixed_mapping_key",
                "kind": "positive",
                "form": "value",
                "summary": "Select one mapping value with the lookup pipeline filter.",
                "yaml": 'inputs.status_labels | lookup("ready")',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "expression_value",
                    "target": "workflow.local_expression.filter.lookup",
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
    validate_help_snippet_registry(payload)
    return payload


def validate_help_snippet_registry(registry: dict[str, JSONObject]) -> None:
    """Validate published help-snippet metadata."""

    for handle, entry in registry.items():
        coverage = entry.get("snippet_coverage")
        if coverage not in {"none", "excerpt_verified", "harness_verified", "runner_verified"}:
            raise ValueError(f"Unsupported snippet coverage for {handle}: {coverage!r}")
        for example in entry.get("canonical_examples", []):
            if not isinstance(example, dict):
                raise ValueError(f"Canonical example for {handle} must be a mapping")
            form = example.get("form")
            if form not in SUPPORTED_SNIPPET_FORMS:
                raise ValueError(f"Unsupported snippet form for {handle}:{example.get('name')}: {form!r}")
            verification = example.get("verification")
            if not isinstance(verification, dict):
                raise ValueError(f"Missing verification metadata for {handle}:{example.get('name')}")
            kind = verification.get("kind")
            if kind not in SUPPORTED_SNIPPET_VERIFICATION_KINDS:
                raise ValueError(f"Unsupported verification kind for {handle}:{example.get('name')}: {kind!r}")
            if kind == "runner_verified":
                if not isinstance(verification.get("world"), str):
                    raise ValueError(f"runner_verified snippet must declare world for {handle}:{example.get('name')}")
                insertion_mode = verification.get("insertion_mode")
                if insertion_mode not in SUPPORTED_SNIPPET_INSERTION_MODES:
                    raise ValueError(
                        f"Unsupported runner insertion mode for {handle}:{example.get('name')}: {insertion_mode!r}"
                    )
                if not isinstance(verification.get("target"), str):
                    raise ValueError(f"runner_verified snippet must declare target for {handle}:{example.get('name')}")
                if "expected_status" not in verification:
                    raise ValueError(f"runner_verified snippet must declare expected_status for {handle}:{example.get('name')}")
