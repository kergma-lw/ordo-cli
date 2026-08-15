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
    "routine_bundle",
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
    "routine_bundle",
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
                "name": "step_if_value_optional_close_comment",
                "kind": "positive",
                "form": "value",
                "summary": "Show a valid `workflow.step.if` value for the case when a close comment is present.",
                "yaml": "is_present(inputs.close_comment)",
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_field",
                    "target": "workflow.step.if",
                    "expected_status": "ok",
                },
            },
            {
                "name": "step_if_optional_close_comment_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Show one complete optional step guarded by `workflow.step.if`.",
                "yaml": '- name: Add close comment\n  if: is_present(inputs.close_comment)\n  uses: gh.issue.comment.add\n  with:\n    repository: inputs.repository\n    issue_number: inputs.issue_number\n    body: inputs.close_comment',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "workflow.step.if",
                    "expected_status": "ok",
                },
            }
        ],
    },
    "workflow.profile": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "workflow_profile_project_local_binding",
                "kind": "positive",
                "form": "workflow_fragment",
                "summary": "Bind one project-local workflow subtree to a fixed execution profile before guards run.",
                "yaml": 'version: 0\nworkflow: inspect-issue\nprofile: backend-default\ninputs:\n  repository: {}\nblocks:\n  - guards:\n      - inputs.repository == "acme/backend"\n  - steps:\n      - name: remember\n        value: "ok"',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "workflow_fragment",
                    "target": "workflow.profile",
                    "expected_status": "ok",
                },
            }
        ],
    },
    "workflow.state_needs": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "workflow_state_needs_shared_state_requirement",
                "kind": "positive",
                "form": "workflow_fragment",
                "summary": "Declare one shared-state requirement before reading that state from let and mutating steps.",
                "yaml": 'version: 0\nworkflow: remember-profile\ninputs:\n  active_profile_key: {}\nstate_needs:\n  shared_state: {}\nlet:\n  active_profile: state.shared_state[inputs.active_profile_key]\nblocks:\n  - steps:\n      - name: remember\n        state_set:\n          state.shared_state["active_profile"]: active_profile',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "workflow_fragment",
                    "target": "workflow.state_needs",
                    "expected_status": "ok",
                },
            }
        ],
    },
    "workflow.state_bindings": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "workflow_state_bindings_shared_state_role",
                "kind": "positive",
                "form": "workflow_fragment",
                "summary": "Bind one workflow state role to one declared playbook state location before reading and mutating durable state.",
                "source_example": "examples.state-bindings",
                "source_excerpt": {
                    "path": "examples/state-bindings.yaml",
                    "start_line": 1,
                    "end_line": 13
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.state-bindings"
                },
            }
        ],
    },
    "workflow.step.profile_switch": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "profile_switch_fixed_literal_value",
                "kind": "positive",
                "form": "value",
                "summary": "Switch later execution to one explicit declared profile with a quoted literal step-field value.",
                "yaml": '"frontend"',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_field",
                    "target": "workflow.step.profile_switch",
                    "expected_status": "ok",
                },
            },
            {
                "name": "profile_switch_step_fragment_with_guard",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Show one complete profile-switch step that changes later execution only when the selected profile is present.",
                "yaml": '- name: switch-profile\n  if: is_present(inputs.selected_profile)\n  profile_switch: inputs.selected_profile',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "workflow.step.profile_switch",
                    "expected_status": "ok",
                },
            }
        ],
    },
    "workflow.step_forms.profile_switch": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "profile_switch_form_minimal_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Use the dedicated profile-switch step form when one named step only changes later execution context.",
                "yaml": '- name: switch-frontend\n  profile_switch: "frontend"',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "workflow.step_forms.profile_switch",
                    "expected_status": "ok",
                },
            }
        ],
    },
    "workflow.step.state_set": {
        "snippet_coverage": "runner_verified",
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
            },
            {
                "name": "state_set_step_fragment_remembers_profile",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Show one complete step fragment that stores a shared-state profile value.",
                "yaml": '- name: remember-profile\n  state_set:\n    state.shared_state["active_profile"]: review',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "workflow.step.state_set",
                    "expected_status": "ok",
                },
            }
        ],
    },
    "workflow.step.state_delete": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "state_delete_fixed_shared_state_key",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Delete one fixed shared-state key directly with a literal key selector.",
                "yaml": 'state_delete: state.shared_state["active_profile"]',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_field",
                    "target": "workflow.step.state_delete",
                    "expected_status": "ok",
                },
            },
            {
                "name": "state_delete_dynamic_task_memory_field",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Delete one state field under a task-memory key that comes from inputs.",
                "yaml": 'state_delete: state.task_memory[inputs.issue_ref].branch',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_field",
                    "target": "workflow.step.state_delete",
                    "expected_status": "ok",
                },
            },
            {
                "name": "state_delete_step_fragment_forgets_branch",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Show one complete step fragment that deletes a remembered task-memory branch value.",
                "yaml": '- name: forget-branch\n  state_delete: state.task_memory[inputs.issue_ref].branch',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "workflow.step.state_delete",
                    "expected_status": "ok",
                },
            }
        ],
    },
    "workflow.step.value": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "step_value_boolean_membership_check",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Compute one boolean membership check as a local step value.",
                "yaml": 'inputs.status | in(inputs.allowed)',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_field",
                    "target": "workflow.step.value",
                    "expected_status": "ok",
                },
            },
            {
                "name": "step_value_step_fragment_with_register",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Show one complete value step that computes a local value and registers it for later reuse.",
                "yaml": '- name: classify-status\n  value: inputs.status | in(inputs.allowed)\n  register: status_allowed',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "workflow.step.value",
                    "expected_status": "ok",
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
    "local-expressions": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "local_expression_boolean_pipeline",
                "kind": "positive",
                "form": "value",
                "summary": "Use one short local-expression pipeline for a workflow-owned boolean decision.",
                "yaml": 'inputs.status | lower | eq("ready")',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "expression_value",
                    "target": "local-expressions",
                    "expected_status": "ok",
                },
            }
        ],
    },
    "adapters": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "adapter_markdown_section_projection",
                "kind": "positive",
                "form": "value",
                "summary": "Project one markdown section through the published adapter surface instead of hand-rolled parsing.",
                "yaml": 'inputs.body | markdown["Tasks"]',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "expression_value",
                    "target": "adapters",
                    "expected_status": "ok",
                },
            }
        ],
    },
    "routine": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "routine_step_fragment_with_args",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Call one project-local routine step with explicit business arguments.",
                "yaml": '- name: run-routine\n  uses: routine.demo.echo\n  with:\n    args:\n      target: inputs.target',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "routine",
                    "expected_status": "ok",
                },
            },
            {
                "name": "routine_step_fragment_with_env_forwarding",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Forward a short explicit list of scalar workflow references into one routine call.",
                "yaml": '- name: collect\n  value:\n    path: "/tmp/demo.txt"\n  register: collect\n- name: run-routine\n  uses: routine.demo.echo\n  with:\n    args:\n      target: inputs.target\n    env:\n      - inputs.repository\n      - step.collect.outputs.value.path',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "routine",
                    "expected_status": "ok",
                },
            },
            {
                "name": "routine_step_fragment_with_register",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Register one routine call so later steps can read its structured outputs explicitly.",
                "yaml": '- name: run-routine\n  uses: routine.demo.echo\n  with:\n    args:\n      target: inputs.target\n  register: routine_result',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "routine",
                    "expected_status": "ok",
                },
            },
            {
                "name": "routine_bundle_registry_and_implementation",
                "kind": "positive",
                "form": "routine_bundle",
                "summary": "Publish one honest routine bundle with registry entry, implementation script, and sample execution contract.",
                "yaml": 'routine_id: demo.echo\nregistry_entry:\n  kind: action\n  summary: Echo one target string through a local helper.\n  args:\n    target:\n      type: string\n      required: true\n  implementation:\n    argv:\n      - .ordo/scripts/echo_target.py\n      - "{target}"\n  outputs:\n    mode: data\n    format: json\n  failure_modes:\n    - runtime_unavailable\nimplementation_path: .ordo/scripts/echo_target.py\nimplementation_text: |\n  #!/usr/bin/env python3\n  import json\n  import sys\n\n  print(json.dumps({"target": sys.argv[1]}))\nsample_args:\n  target: demo-target\nexpected_stdout_json:\n  target: demo-target',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "routine_bundle",
                    "target": "routine",
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
