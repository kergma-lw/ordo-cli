"""Canonical help snippets and snippet-coverage metadata."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from .human import HumanDeclaration, declare_human, human_mapping
from .json import JSONObject


SUPPORTED_SNIPPET_FORMS = {
    "graph_bundle",
    "value",
    "field_fragment",
    "step_fragment",
    "workflow_fragment",
    "routine_bundle",
    "state_bundle",
}

SUPPORTED_SNIPPET_VERIFICATION_KINDS = {
    "harness_verified",
    "excerpt_verified",
    "runner_verified",
}

SUPPORTED_SNIPPET_INSERTION_MODES = {
    "graph_bundle",
    "expression_value",
    "step_field",
    "step_fragment",
    "workflow_fragment",
    "routine_bundle",
    "state_bundle",
}


# Focused GitHub help shows one complete, usable workflow per operation. The
# other verified variants remain available to maintain their distinct policies.
_TEXT_CANONICAL_EXAMPLE_NAMES = {
    "connector.gh.pr": frozenset({"gh_pr_async_merge_head"}),
    "connector.gh.pr.create": frozenset({"gh_pr_create_new_only"}),
    "connector.gh.pr.list": frozenset({"gh_pr_list_exactly_one_open"}),
    "connector.gh.pr.merge": frozenset({"gh_pr_async_merge_head"}),
    "connector.gh.pr.merge.request": frozenset({"gh_pr_async_merge_head_context"}),
    "connector.gh.pr.checks": frozenset({"gh_pr_checks_step"}),
}


def text_canonical_examples(handle: str, examples: list[JSONObject]) -> list[JSONObject]:
    """Return only canonical examples suitable for reader-facing text help."""

    names = _TEXT_CANONICAL_EXAMPLE_NAMES.get(handle)
    return [example for example in examples if names is None or example["name"] in names]


SNIPPET_COVERAGE_HUMAN = declare_human({
    "title": "Example coverage",
    "goal": "See which public references have checked examples you can use as a starting point.",
    "summary": "Coverage reports whether a reference has no checked example, an excerpt checked against a source example, or an example checked by a run. Some conceptual references intentionally have no checked example.",
    "sections": [],
})


def snippet_coverage_human(handles: list[JSONObject], coverage_counts: dict[str, int]) -> HumanDeclaration:
    """Return reader-facing coverage guidance beside the snippet registry."""

    content = dict(human_mapping(SNIPPET_COVERAGE_HUMAN))
    content["sections"] = [
        {
            "heading": "Coverage summary",
            "items": [
                f"Public references: {len(handles)}.",
                f"No checked example: {coverage_counts.get('none', 0)}.",
                f"Excerpt checked against its source: {coverage_counts.get('excerpt_verified', 0)}.",
                f"Example checked by a run: {coverage_counts.get('runner_verified', 0)}.",
            ],
        },
        {
            "heading": "When no checked example is listed",
            "items": [
                "No checked example can mean the reference is intentionally conceptual or that no small example would teach it honestly; it is not a request to create an example just to raise coverage.",
                "Start with the related references in `ordo-help describe <handle>`. For an end-to-end workflow shape, inspect the repository examples guide before deciding whether a focused example is useful.",
            ],
            "references": [
                {"handle": "examples", "summary": "Complete repository workflows to use when a focused snippet is not the right teaching form"},
                {"handle": "workflow.run_contract", "summary": "Run and repeated-work guidance, including the focused fan-out example"},
            ],
        },
        {
            "heading": "References",
            "items": [
                f"{item['handle']}: {item['snippet_coverage'].replace('_', ' ')}."
                for item in handles
            ],
        },
    ]
    return declare_human(content)  # type: ignore[arg-type]


_REPO_ROOT = Path(__file__).resolve().parents[3]


_COMPOSE_LIFECYCLE_WORKFLOW = '''version: 0
workflow: compose-lifecycle-decisions
inputs:
  service: {}
  start_project: {}
  remove_service: {}
blocks:
- steps:
  - name: inspect-project
    uses: compose.project
    register: project
  - name: require-project-start-decision
    gate: inputs.start_project and step.project.outputs.state != "running"
  - name: start-project
    uses: compose.start
    register: started
  - name: require-project-running
    gate: step.started.outputs.state == "running"
  - name: inspect-service
    uses: compose.service
    with:
      service: inputs.service
    register: service_before_cleanup
  - name: require-service-cleanup-decision
    gate: inputs.remove_service
  - name: stop-service
    uses: compose.stop
    with:
      service: inputs.service
    register: stopped
  - name: require-service-stopped
    gate: step.stopped.outputs.state == "stopped"
  - name: remove-service
    uses: compose.remove
    with:
      service: inputs.service
    register: removed
  - name: require-service-absent
    gate: step.removed.outputs.state == "absent"
  - name: publish-lifecycle-results
    publish:
      project_state_before_start: step.project.outputs.state
      started_project: step.started.outputs.changed
      service_state_before_cleanup: step.service_before_cleanup.outputs.state
      stopped_service: step.stopped.outputs.changed
      removed_service: step.removed.outputs.changed'''


HELP_SNIPPET_REGISTRY: dict[str, JSONObject] = {
    "connector.compose.project": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [{
            "name": "compose_lifecycle_decisions", "kind": "positive", "form": "workflow_fragment",
            "summary": "Inspect the configured Compose project, make the start decision explicit, then save and check the action result before moving to service cleanup.",
            "yaml": _COMPOSE_LIFECYCLE_WORKFLOW,
            "verification": {"kind": "runner_verified", "world": "default", "insertion_mode": "workflow_fragment", "target": "connector.compose.project", "expected_status": "ok"},
        }],
    },
    "connector.compose.service": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [{
            "name": "compose_lifecycle_decisions", "kind": "positive", "form": "workflow_fragment",
            "summary": "Inspect the named service before cleanup, save its observed state, and require an explicit cleanup decision before changing it.",
            "yaml": _COMPOSE_LIFECYCLE_WORKFLOW,
            "verification": {"kind": "runner_verified", "world": "default", "insertion_mode": "workflow_fragment", "target": "connector.compose.service", "expected_status": "ok"},
        }],
    },
    "connector.compose.start": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [{
            "name": "compose_lifecycle_decisions", "kind": "positive", "form": "workflow_fragment",
            "summary": "Start the configured project only after an explicit decision, register the result, and require `running` before later service work.",
            "yaml": _COMPOSE_LIFECYCLE_WORKFLOW,
            "verification": {"kind": "runner_verified", "world": "default", "insertion_mode": "workflow_fragment", "target": "connector.compose.start", "expected_status": "ok"},
        }],
    },
    "connector.compose.stop": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [{
            "name": "compose_lifecycle_decisions", "kind": "positive", "form": "workflow_fragment",
            "summary": "Stop one named service only after an explicit cleanup decision, save the result, and require `stopped` before removal.",
            "yaml": _COMPOSE_LIFECYCLE_WORKFLOW,
            "verification": {"kind": "runner_verified", "world": "default", "insertion_mode": "workflow_fragment", "target": "connector.compose.stop", "expected_status": "ok"},
        }],
    },
    "connector.compose.remove": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [{
            "name": "compose_lifecycle_decisions", "kind": "positive", "form": "workflow_fragment",
            "summary": "Remove the named service only after the saved stop result is `stopped`, then save and require the final `absent` result before publishing cleanup facts.",
            "yaml": _COMPOSE_LIFECYCLE_WORKFLOW,
            "verification": {"kind": "runner_verified", "world": "default", "insertion_mode": "workflow_fragment", "target": "connector.compose.remove", "expected_status": "ok"},
        }],
    },
    "connector.fs.file": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "fs_file_observation_steps",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Supply file_path, register the fs.file probe, and publish basename, byte size, line count, and content-derived character count without publishing full content. The length filter counts characters, not lines.",
                "source_example": "fs-file-inspection",
                "source_excerpt": {"path": "examples/fs-file-inspection.yaml", "start_line": 8, "end_line": 18},
                "verification": {"kind": "runner_verified", "world": "default", "insertion_mode": "step_fragment", "target": "connector.fs.file", "expected_status": "ok"},
            },
            {
                "name": "fs_file_observation_workflow",
                "kind": "positive",
                "form": "workflow_fragment",
                "summary": "A complete observer workflow requires file_path and publishes a summary rather than full content. Content and metadata come from one observed file, not an atomic snapshot.",
                "source_example": "fs-file-inspection",
                "source_excerpt": {"path": "examples/fs-file-inspection.yaml", "start_line": 1, "end_line": 18},
                "verification": {"kind": "runner_verified", "world": "default", "insertion_mode": "workflow_fragment", "target": "connector.fs.file", "expected_status": "ok"},
            },
        ],
    },
    "examples.let-bindings": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "guard_and_publish_branch_label",
                "kind": "positive",
                "form": "workflow_fragment",
                "summary": "Use let to name reusable expressions: should_run controls admission, while branch formats the input type and issue number. With the defaults, publish emits branch: task/7; enabled: false blocks publication. Publish returns data, unlike shell.command execution or Git branch creation. Runner verification validates the full workflow shape without execution; targeted example tests cover execution safety.",
                "source_example": "examples.let-bindings",
                "source_excerpt": {"path": "examples/let-bindings.yaml", "start_line": 1, "end_line": 16},
                "verification": {"kind": "runner_verified", "world": "default", "insertion_mode": "workflow_fragment", "target": "examples.let-bindings", "expected_status": "ok"},
            },
        ],
    },
    "examples.set-active-task-from-gitx": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "native_task_activation",
                "kind": "positive",
                "form": "workflow_fragment",
                "summary": "Supply required repository and project_id inputs and bind the task_memory state role through the playbook; allowed_issue_types is a list (default [Task, Bug]), not CSV. Guards require boolean allow_backlog, one clean worktree, and an open issue. Add membership, then read project policy: missing type blocks, missing status is allowed, Done/In review block, and Backlog needs permission. Set Status to In progress before Git work. Branch naming and remembered issue values use inputs, not the project type. Fetch the configured remote once (no branch-specific fetch or pull), require its remote-tracking base, then switch and fast-forward an existing local base. A failed base switch stops the sequence. Reuse a target branch or create it from the local base, otherwise the remote-tracking base; separate creation and switching can leave a branch on failure. Write task state only after switching. Earlier membership, status, Git, and individual state writes are not rolled back on later failure. Only nonempty post_open_command runs as explicit trusted code; never interpolate ordinary issue data into it. This retained migration hook is not permission to author new shell.command steps; the workflow-rules prohibition still applies. This illustrative example is not the canonical .ordo workflow; demo profile project IDs make no operational promise. Runner verification validates the complete source shape, including required inputs and state_needs, without Git/GitHub execution, state persistence, or hook execution.",
                "source_example": "examples.set-active-task-from-gitx",
                "source_excerpt": {"path": "examples/set-active-task-from-gitx.yaml", "start_line": 1, "end_line": 155},
                "verification": {"kind": "runner_verified", "world": "default", "insertion_mode": "workflow_fragment", "target": "examples.set-active-task-from-gitx", "expected_status": "ok"},
            },
        ],
    },
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
            {
                "name": "state_read_before_write",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Read the old profile before storing a profile for a future run; reuse the registered value afterward.",
                "yaml": '- name: read-profile\n  value: state.shared_state["active_profile"]\n  register: previous_profile\n- name: remember-profile\n  state_set:\n    state.shared_state["active_profile"]: review\n- name: report-previous-profile\n  publish:\n    previous_profile: step.previous_profile.outputs.value',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "workflow.step.state_set",
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
    "playbook.workflows": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "playbook_workflows_catalog_entry",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Publish one named workflow entry with a description, selection guidance, fixed inputs, working directory, and state bindings. Use `workflows show` to see the caller-facing interface and `--json` to inspect the complete declaration.",
                "yaml": 'workflows:\n  remember-profile:\n    file: ./playbook-workflow-target.yaml\n    description: Read one remembered profile from shared state\n    category: inspect\n    when: Use when you need one state-backed profile lookup before choosing the next workflow.\n    with:\n      active_profile_key: active_profile\n      repo_dir: .\n    working_directory: ${inputs.repo_dir}\n    state_bindings:\n      shared_state: shared_state',
                "source_example": "examples.playbook-workflows",
                "source_excerpt": {
                    "path": "examples/playbook-workflows.yaml",
                    "start_line": 7,
                    "end_line": 18
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.playbook-workflows"
                },
            }
        ],
    },
    "playbook.workflows.file": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "playbook_workflows_file_entry",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Bind one published workflow name to the workflow file that the playbook should load for that entry.",
                "yaml": 'file: ./playbook-workflow-target.yaml',
                "source_example": "examples.playbook-workflows",
                "source_excerpt": {
                    "path": "examples/playbook-workflows.yaml",
                    "start_line": 9,
                    "end_line": 9
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.playbook-workflows"
                },
            }
        ],
    },
    "workflow.inputs": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "documented_required_and_optional_inputs",
                "kind": "positive",
                "form": "workflow_fragment",
                "summary": "Document required and optional root inputs beside their declarations. The playbook supplies the state key and optional directory separately; concrete bindings without caller slots stay hidden from plain inputs. Plain show preserves default/description/hint when declared, omits top-level launch_profile and input caller_slot/sources/coverage, and reports caller-slot obligation in required without adding optional. It adds top-level discovery.workflow.input_source_missing warnings only for required workflow declarations with coverage missing; optional missing declarations do not warn. No qualifying declaration means no warnings field. --json retains the unchanged full declaration and launch-profile contract. Excerpt verification checks source parity, not CLI discovery, activation, or review outcomes.",
                "source_excerpt": {"path": "examples/playbook-workflow-target.yaml", "start_line": 1, "end_line": 16},
                "verification": {"kind": "excerpt_verified", "example": "examples.playbook-workflows"},
            }
        ],
    },
    "workflow.inputs_contract": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "documented_input_contract",
                "kind": "positive",
                "form": "workflow_fragment",
                "summary": "A required input and an explicitly optional input both carry descriptions; neither declares a default, so workflows show must not invent default: null. Caller exposure belongs to playbook.workflows.with. Plain show displays caller slots, omits top-level launch_profile and input caller_slot/sources/coverage, and reports caller-slot obligation in required without adding optional. Its conditional top-level discovery.workflow.input_source_missing warnings use workflow declaration requiredness and coverage missing, not displayed required. Optional missing declarations do not warn; no qualifying declaration means no warnings field. --json retains every declaration and all existing fields unchanged. Excerpt verification checks source parity, not CLI discovery, activation, or review outcomes.",
                "source_excerpt": {"path": "examples/playbook-workflow-target.yaml", "start_line": 1, "end_line": 16},
                "verification": {"kind": "excerpt_verified", "example": "examples.playbook-workflows"},
            }
        ],
    },
    "playbook.workflows.with": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "playbook_workflows_with_entry",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Supply the state key and directory as fixed values owned by this workflow entry. Use caller placeholders when the value must instead be provided for each run.",
                "yaml": 'with:\n  active_profile_key: active_profile\n  repo_dir: .',
                "source_example": "examples.playbook-workflows",
                "source_excerpt": {
                    "path": "examples/playbook-workflows.yaml",
                    "start_line": 13,
                    "end_line": 15
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.playbook-workflows"
                },
            },
            {
                "name": "playbook_required_and_optional_caller_inputs",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Expose the state key with active_profile_key: and the optional directory with repo_dir?:. Both plain workflows show and --json retain these caller inputs; a required slot still demands caller input even if another source provides coverage. Either slot form suppresses discovery.workflow.input_source_missing warnings: plain top-level warnings appears only for required workflow declarations with coverage missing, and is omitted when none qualify. Plain show omits top-level launch_profile and input caller_slot/sources/coverage; other record fields are preserved except required, which is true for a required slot and false for an optional slot. No optional field is added. --json keeps all fields unchanged. Excerpt verification checks source parity, not CLI discovery, activation, or review outcomes.",
                "source_excerpt": {"path": "examples/playbook-workflows.yaml", "start_line": 19, "end_line": 26},
                "verification": {"kind": "excerpt_verified", "example": "examples.playbook-workflows"},
            }
        ],
    },
    "playbook.workflows.description": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "playbook_workflows_description_entry",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Publish one short summary that tells operators what this workflow entry does.",
                "yaml": 'description: Read one remembered profile from shared state',
                "source_example": "examples.playbook-workflows",
                "source_excerpt": {
                    "path": "examples/playbook-workflows.yaml",
                    "start_line": 10,
                    "end_line": 10
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.playbook-workflows"
                },
            }
        ],
    },
    "playbook.workflows.category": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "playbook_workflows_category_entry",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Group one published workflow under a lightweight catalog family label.",
                "yaml": 'category: inspect',
                "source_example": "examples.playbook-workflows",
                "source_excerpt": {
                    "path": "examples/playbook-workflows.yaml",
                    "start_line": 11,
                    "end_line": 11
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.playbook-workflows"
                },
            }
        ],
    },
    "playbook.workflows.when": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "playbook_workflows_when_entry",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Teach operators when this published workflow is the right entry to run.",
                "yaml": 'when: Use when you need one state-backed profile lookup before choosing the next workflow.',
                "source_example": "examples.playbook-workflows",
                "source_excerpt": {
                    "path": "examples/playbook-workflows.yaml",
                    "start_line": 12,
                    "end_line": 12
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.playbook-workflows"
                },
            }
        ],
    },
    "playbook.workflows.working_directory": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "playbook_workflows_working_directory_entry",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Override one workflow entry's execution directory through an activation-input expression resolved before the workflow starts.",
                "yaml": 'working_directory: ${inputs.repo_dir}',
                "source_example": "examples.playbook-workflows",
                "source_excerpt": {
                    "path": "examples/playbook-workflows.yaml",
                    "start_line": 16,
                    "end_line": 16
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.playbook-workflows"
                },
            }
        ],
    },
    "playbook.workflows.state_bindings": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "playbook_workflows_state_bindings_entry",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Bind the workflow entry's declared shared_state role to the named playbook state location.",
                "yaml": 'state_bindings:\n  shared_state: shared_state',
                "source_example": "examples.playbook-workflows",
                "source_excerpt": {
                    "path": "examples/playbook-workflows.yaml",
                    "start_line": 17,
                    "end_line": 18
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.playbook-workflows"
                },
            }
        ],
    },
    "playbook.version": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "playbook_version_marker",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Start one playbook document with the required version marker before the rest of the top-level launch catalog.",
                "yaml": "version: 1\nstates:\n  shared_state:\n    path: .ordo/example-state.json",
                "source_example": "examples.playbook-connectors",
                "source_excerpt": {
                    "path": "examples/playbook-connectors.yaml",
                    "start_line": 1,
                    "end_line": 4
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.playbook-connectors"
                },
            }
        ],
    },
    "playbook.connectors": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "playbook_connector_defaults_block",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Declare one repository-wide Compose bootstrap block that workflows inherit before profile-specific connector overrides are considered.",
                "yaml": "connectors:\n  compose:\n    directory: ./deploy\n    file: compose.prod.yaml",
                "source_example": "examples.playbook-connectors",
                "source_excerpt": {
                    "path": "examples/playbook-connectors.yaml",
                    "start_line": 7,
                    "end_line": 10
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.playbook-connectors"
                },
            }
        ],
    },
    "profile.connectors": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "profile_connector_override_block",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Bind one profile-scoped Compose context block that applies only when this profile is selected.",
                "source_excerpt": {
                    "path": "profiles/compose-review.yaml",
                    "start_line": 3,
                    "end_line": 7
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "profiles.compose-review"
                },
            }
        ],
    },
    "profile.inputs": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "profile_input_defaults_block",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Publish one profile-scoped input-default block that supplies declared workflow inputs only when they are still missing at activation time.",
                "source_excerpt": {
                    "path": "profiles/backend-default.yaml",
                    "start_line": 3,
                    "end_line": 5
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "profiles.backend-default"
                },
            }
        ],
    },
    "profile.working_directory": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "profile_working_directory_expression",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Publish one profile-scoped execution directory that resolves from an activation input relative to the playbook directory.",
                "source_excerpt": {
                    "path": "profiles/frontend-workdir.yaml",
                    "start_line": 3,
                    "end_line": 6
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "profiles.frontend-workdir"
                },
            }
        ],
    },
    "profile.name": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "profile_declared_name",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Declare the profile document's stable internal name so selection surfaces can refer to it explicitly.",
                "source_excerpt": {
                    "path": "profiles/read-only-review.yaml",
                    "start_line": 1,
                    "end_line": 1
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "profiles.read-only-review"
                },
            }
        ],
    },
    "profile.checks": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "profile_check_labels",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Publish one profile-scoped list of named check labels so the profile advertises its expected verification posture.",
                "source_excerpt": {
                    "path": "profiles/backend-default.yaml",
                    "start_line": 7,
                    "end_line": 9
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "profiles.backend-default"
                },
            }
        ],
    },
    "profile.launchers": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "profile_legacy_launcher_block",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Publish one deprecated profile-scoped launcher record so an older workflow can still reference a named launcher during migration.",
                "source_excerpt": {
                    "path": "profiles/frontend-launcher.yaml",
                    "start_line": 5,
                    "end_line": 10
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "profiles.frontend-launcher"
                },
            }
        ],
    },
    "workflow.version": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "workflow_version_marker",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Start one workflow document with the required version marker before the rest of the top-level workflow contract.",
                "source_excerpt": {
                    "path": "examples/minimal.yaml",
                    "start_line": 1,
                    "end_line": 3
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.minimal"
                },
            }
        ],
    },
    "workflow.workflow": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "workflow_declared_name",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Declare the workflow document's stable contract name before the block structure begins.",
                "source_excerpt": {
                    "path": "examples/minimal.yaml",
                    "start_line": 2,
                    "end_line": 3
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.minimal"
                },
            }
        ],
    },
    "workflow.run.run": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "run_named_target_field",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Select one named reusable run target for a runtime invocation step instead of inlining the repeated body locally.",
                "source_excerpt": {
                    "path": "examples/run-fan-out.yaml",
                    "start_line": 7,
                    "end_line": 9
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.run-fan-out"
                },
            }
        ],
    },
    "workflow.run.with": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "run_argument_bindings_block",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Bind explicit caller-scoped values into one named run target instead of letting the callee read caller context implicitly.",
                "source_excerpt": {
                    "path": "examples/run-fan-out.yaml",
                    "start_line": 9,
                    "end_line": 12
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.run-fan-out"
                },
            }
        ],
    },
    "workflow.run.for_each": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "run_bounded_fan_out_source",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Repeat one invocation-shaped step over an explicit array-valued item source.",
                "source_excerpt": {
                    "path": "examples/run-fan-out.yaml",
                    "start_line": 12,
                    "end_line": 14
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.run-fan-out"
                },
            }
        ],
    },
    "workflow.run.if": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "run_outer_if_condition",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Gate the whole invocation step with one outer caller-scoped condition before fan-out or inline body execution begins.",
                "source_excerpt": {
                    "path": "examples/run-fan-out.yaml",
                    "start_line": 13,
                    "end_line": 15
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.run-fan-out"
                },
            }
        ],
    },
    "workflow.run.gate": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "run_outer_gate_condition",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Declare one outer admission gate for a run invocation when the real question is whether the whole invocation may proceed at all.",
                "source_excerpt": {
                    "path": "examples/run-fan-out.yaml",
                    "start_line": 18,
                    "end_line": 22
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.run-fan-out"
                },
            }
        ],
    },
    "workflow.run.register": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "run_aggregate_register_name",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Capture the aggregate results of a run invocation or fan-out step under one explicit outer register name.",
                "source_excerpt": {
                    "path": "examples/run-fan-out.yaml",
                    "start_line": 13,
                    "end_line": 16
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.run-fan-out"
                },
            }
        ],
    },
    "workflow.run.steps": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "run_inline_repeated_body",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Keep one short local repeated body inline under for_each when a named run target would be heavier than necessary.",
                "source_excerpt": {
                    "path": "examples/run-fan-out.yaml",
                    "start_line": 25,
                    "end_line": 31
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.run-fan-out"
                },
            }
        ],
    },
    "workflow.step.name": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "step_declared_identity",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Give one step a stable local identity so later workflow surfaces can refer to it explicitly.",
                "source_excerpt": {
                    "path": "examples/inspect-issue.yaml",
                    "start_line": 10,
                    "end_line": 10
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.inspect-issue"
                },
            }
        ],
    },
    "workflow.step.condition": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "step_optional_if_condition",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Use one step-level if condition when the step is locally optional inside an already-valid path.",
                "source_excerpt": {
                    "path": "examples/project-issue-membership.yaml",
                    "start_line": 17,
                    "end_line": 19
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.project-issue-membership"
                },
            },
            {
                "name": "step_admission_gate_condition",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Use one gate condition when the real question is whether the protected invocation may proceed at all.",
                "source_excerpt": {
                    "path": "examples/run-fan-out.yaml",
                    "start_line": 21,
                    "end_line": 24
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.run-fan-out"
                },
            }
        ],
    },
    "workflow.step.outputs": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "step_outputs_read_path",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Read one earlier registered step result through the explicit step.<register>.outputs... surface instead of inventing implicit shared context.",
                "source_excerpt": {
                    "path": "examples/project-issue-membership.yaml",
                    "start_line": 17,
                    "end_line": 18
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.project-issue-membership"
                },
            }
        ],
    },
    "workflow.step_forms.operation_call": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "operation_call_form_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Use the dedicated operation-call step form when one named step's primary job is invoking one published operation surface through uses.",
                "source_excerpt": {
                    "path": "examples/inspect-issue.yaml",
                    "start_line": 10,
                    "end_line": 15
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.inspect-issue"
                },
            }
        ],
    },
    "workflow.step_forms.run_invocation": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "run_invocation_form_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Use the dedicated run-invocation step form when one named step invokes a workflow fragment target with optional fan-out and aggregate capture.",
                "source_excerpt": {
                    "path": "examples/run-fan-out.yaml",
                    "start_line": 8,
                    "end_line": 15
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.run-fan-out"
                },
            }
        ],
    },
    "workflow.step_forms.inline_fan_out_invocation": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "inline_fan_out_form_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Use the dedicated inline fan-out form when a short local repeated body should stay inline under one explicit for_each step.",
                "source_excerpt": {
                    "path": "examples/run-fan-out.yaml",
                    "start_line": 25,
                    "end_line": 31
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.run-fan-out"
                },
            }
        ],
    },
    "profile.overrides": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "profile_overrides_block",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Publish one profile-scoped override record with a named target, structured data, and a short reason note.",
                "yaml": "overrides:\n  - target: local.issue-triage\n    with:\n      default_label: bug\n      board: intake\n    reason: Share one profile-scoped triage adaptation record.",
                "source_excerpt": {
                    "path": "examples/profile-overrides.yaml",
                    "start_line": 2,
                    "end_line": 7
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "profile-overrides"
                }
            }
        ],
    },
    "profile.overrides.target": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "profile_override_target_field",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Name which integration or local convention should read this override record.",
                "yaml": "  - target: local.issue-triage",
                "source_excerpt": {
                    "path": "examples/profile-overrides.yaml",
                    "start_line": 3,
                    "end_line": 3
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "profile-overrides"
                }
            }
        ],
    },
    "profile.overrides.with": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "profile_override_with_payload",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Attach structured data that the named target may use.",
                "yaml": "    with:\n      default_label: bug\n      board: intake",
                "source_excerpt": {
                    "path": "examples/profile-overrides.yaml",
                    "start_line": 4,
                    "end_line": 6
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "profile-overrides"
                }
            }
        ],
    },
    "profile.overrides.reason": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "profile_override_reason_note",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Annotate the override record with one short explanation for later readers.",
                "yaml": "    reason: Share one profile-scoped triage adaptation record.",
                "source_excerpt": {
                    "path": "examples/profile-overrides.yaml",
                    "start_line": 7,
                    "end_line": 7
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "profile-overrides"
                }
            }
        ],
    },
    "connector.gh.project": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "gh_project_probe_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Confirm one GitHub Project identity before branching into field-level or membership-level project logic.",
                "source_example": "project-field-probes",
                "source_excerpt": {
                    "path": "examples/project-field-probes.yaml",
                    "start_line": 8,
                    "end_line": 12
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "project-field-probes"
                }
            },
            {
                "name": "gh_project_field_probe_flow",
                "kind": "positive",
                "form": "workflow_fragment",
                "summary": "Inspect one project, one named field, and one candidate selectable option, then publish a compact readiness summary.",
                "source_example": "project-field-probes",
                "source_excerpt": {
                    "path": "examples/project-field-probes.yaml",
                    "start_line": 1,
                    "end_line": 30
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "project-field-probes"
                }
            }
        ],
    },
    "connector.gh.repo": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "gh_repo_probe_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Inspect one GitHub repository's normalized identity and fork relationship before deciding whether hosted fork sync applies.",
                "source_example": "gh-repo-sync",
                "source_excerpt": {
                    "path": "examples/gh-repo-sync.yaml",
                    "start_line": 8,
                    "end_line": 10
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "gh-repo-sync"
                }
            },
            {
                "name": "gh_repo_sync_flow",
                "kind": "positive",
                "form": "workflow_fragment",
                "summary": "Inspect one hosted fork repository, sync its default branch from the parent repository, then publish the synced branch summary.",
                "source_example": "gh-repo-sync",
                "source_excerpt": {
                    "path": "examples/gh-repo-sync.yaml",
                    "start_line": 1,
                    "end_line": 18
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "gh-repo-sync"
                }
            }
        ],
    },
    "connector.gh.repo.sync": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "gh_repo_sync_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Sync one hosted GitHub fork repository's default branch from its parent repository through the published repo.sync action.",
                "source_example": "gh-repo-sync",
                "source_excerpt": {
                    "path": "examples/gh-repo-sync.yaml",
                    "start_line": 11,
                    "end_line": 13
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "gh-repo-sync"
                }
            }
        ],
    },
    "connector.gh.repo.actions.permissions": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "gh_repo_actions_permissions_probe_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Read one repository's GitHub Actions permissions before toggling or restoring the hosted Actions enabled state.",
                "source_example": "gh-repo-actions-permissions",
                "source_excerpt": {
                    "path": "examples/gh-repo-actions-permissions.yaml",
                    "start_line": 8,
                    "end_line": 10
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "gh-repo-actions-permissions"
                }
            },
            {
                "name": "gh_repo_actions_permissions_flow",
                "kind": "positive",
                "form": "workflow_fragment",
                "summary": "Read repository Actions permissions, disable Actions explicitly, then restore the prior enabled state through separate leaf actions.",
                "source_example": "gh-repo-actions-permissions",
                "source_excerpt": {
                    "path": "examples/gh-repo-actions-permissions.yaml",
                    "start_line": 1,
                    "end_line": 19
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "gh-repo-actions-permissions"
                }
            }
        ],
    },
    "connector.gh.repo.actions.permissions.set": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "gh_repo_actions_permissions_set_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Set one repository's GitHub Actions enabled flag as an explicit leaf mutation step.",
                "source_example": "gh-repo-actions-permissions",
                "source_excerpt": {
                    "path": "examples/gh-repo-actions-permissions.yaml",
                    "start_line": 11,
                    "end_line": 15
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "gh-repo-actions-permissions"
                }
            }
        ],
    },
    "connector.gh.project.field": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "gh_project_field_probe_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Inspect one named GitHub Project field and register its kind and option metadata for later decisions.",
                "source_example": "project-field-probes",
                "source_excerpt": {
                    "path": "examples/project-field-probes.yaml",
                    "start_line": 13,
                    "end_line": 18
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "project-field-probes"
                }
            }
        ],
    },
    "connector.gh.project.field.option": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "gh_project_field_option_probe_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Check whether one named selectable value is valid for the inspected GitHub Project field.",
                "source_example": "project-field-probes",
                "source_excerpt": {
                    "path": "examples/project-field-probes.yaml",
                    "start_line": 19,
                    "end_line": 25
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "project-field-probes"
                }
            }
        ],
    },
    "connector.gh.project.issue": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "gh_project_issue_probe_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Inspect whether one issue is already attached to the target GitHub Project before deciding whether to add it or mutate its fields.",
                "source_example": "project-issue-membership",
                "source_excerpt": {
                    "path": "examples/project-issue-membership.yaml",
                    "start_line": 10,
                    "end_line": 16
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.gh.project.issue",
                    "expected_status": "ok"
                }
            },
            {
                "name": "gh_project_issue_membership_flow",
                "kind": "positive",
                "form": "workflow_fragment",
                "summary": "Probe one issue's project membership, attach it if needed, then set representative single-select, number, and iteration fields through typed project issue surfaces.",
                "source_example": "project-issue-membership",
                "source_excerpt": {
                    "path": "examples/project-issue-membership.yaml",
                    "start_line": 1,
                    "end_line": 48
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "workflow_fragment",
                    "target": "connector.gh.project.issue",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.gh.project.issue.add": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "gh_project_issue_add_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Attach the issue to the target GitHub Project only when the earlier membership probe reported exists=false.",
                "source_example": "project-issue-membership",
                "source_excerpt": {
                    "path": "examples/project-issue-membership.yaml",
                    "start_line": 17,
                    "end_line": 24
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.gh.project.issue.add",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.gh.project.issue.field_iteration.set": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "gh_project_issue_field_iteration_set_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Move the project-backed issue into one named iteration after membership is already ensured.",
                "source_example": "project-issue-membership",
                "source_excerpt": {
                    "path": "examples/project-issue-membership.yaml",
                    "start_line": 33,
                    "end_line": 40
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.gh.project.issue.field_iteration.set",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.gh.project.issue.field_number.set": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "gh_project_issue_field_number_set_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Write one numeric project field such as Estimate after the issue is attached to the project.",
                "source_example": "project-issue-membership",
                "source_excerpt": {
                    "path": "examples/project-issue-membership.yaml",
                    "start_line": 25,
                    "end_line": 32
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.gh.project.issue.field_number.set",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.gh.project.issue.field_single_select.set": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "gh_project_issue_field_single_select_set_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Set one selectable project field such as Status by its visible option name after membership is ensured.",
                "source_example": "project-issue-membership",
                "source_excerpt": {
                    "path": "examples/project-issue-membership.yaml",
                    "start_line": 41,
                    "end_line": 48
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.gh.project.issue.field_single_select.set",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.gh.project.items": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "gh_project_items_probe_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Scan one GitHub Project for matching items before branching on collection size or reusing the matched item list later.",
                "source_example": "project-item-collections",
                "source_excerpt": {
                    "path": "examples/project-item-collections.yaml",
                    "start_line": 8,
                    "end_line": 16
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.gh.project.items",
                    "expected_status": "ok"
                }
            },
            {
                "name": "gh_project_items_collection_flow",
                "kind": "positive",
                "form": "workflow_fragment",
                "summary": "Load one light project-item collection first, then load richer item details for an explicit matched subset before publishing a compact summary.",
                "source_example": "project-item-collections",
                "source_excerpt": {
                    "path": "examples/project-item-collections.yaml",
                    "start_line": 1,
                    "end_line": 33
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "workflow_fragment",
                    "target": "connector.gh.project.items",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.gh.project.items.details": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "gh_project_items_details_probe_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Load richer project-backed content details such as state and label_names for a previously narrowed project item subset.",
                "source_example": "project-item-collections",
                "source_excerpt": {
                    "path": "examples/project-item-collections.yaml",
                    "start_line": 17,
                    "end_line": 28
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.gh.project.items.details",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.git.branch": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "git_branch_probe_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Read the current checkout branch before making a branch-specific decision or publishing branch context.",
                "source_example": "git-branch-management",
                "source_excerpt": {
                    "path": "examples/git-branch-management.yaml",
                    "start_line": 8,
                    "end_line": 10
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.git.branch",
                    "expected_status": "ok"
                }
            },
            {
                "name": "git_branch_management_flow",
                "kind": "positive",
                "form": "workflow_fragment",
                "summary": "Read the current branch and branch inventory, create a feature branch, switch to it, then clean up one stale local branch.",
                "source_example": "git-branch-management",
                "source_excerpt": {
                    "path": "examples/git-branch-management.yaml",
                    "start_line": 1,
                    "end_line": 31
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "workflow_fragment",
                    "target": "connector.git.branch",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.git.branch.create": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "git_branch_create_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Create one new local feature branch from HEAD without switching the current checkout automatically.",
                "source_example": "git-branch-management",
                "source_excerpt": {
                    "path": "examples/git-branch-management.yaml",
                    "start_line": 14,
                    "end_line": 18
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.git.branch.create",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.git.branch.delete": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "git_branch_delete_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Delete one stale local branch with the default force: false behavior (git branch -d), preserving Git's merged-branch check.",
                "source_example": "git-branch-management",
                "source_excerpt": {
                    "path": "examples/git-branch-management.yaml",
                    "start_line": 23,
                    "end_line": 26
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.git.branch.delete",
                    "expected_status": "ok"
                }
            },
            {
                "name": "git_branch_delete_force_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "After independently verifying squash-merge cleanup eligibility, explicitly select git branch -D with force: true. Default and checked-out branch protections still apply.",
                "source_example": "git-branch-management",
                "source_excerpt": {
                    "path": "examples/git-branch-management.yaml",
                    "start_line": 32,
                    "end_line": 37
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.git.branch.delete",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.git.branch.switch": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "git_branch_switch_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Switch the current checkout onto the created feature branch before later branch-specific work begins.",
                "source_example": "git-branch-management",
                "source_excerpt": {
                    "path": "examples/git-branch-management.yaml",
                    "start_line": 19,
                    "end_line": 22
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.git.branch.switch",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.git.branches": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "git_branches_probe_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Load the branch inventory when the workflow needs the available local and remote branch set instead of only the current branch.",
                "source_example": "git-branch-management",
                "source_excerpt": {
                    "path": "examples/git-branch-management.yaml",
                    "start_line": 11,
                    "end_line": 13
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.git.branches",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.git.commit.create": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "git_commit_create_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Create one ordinary Git commit from the current index after the staged changes are ready.",
                "source_example": "git-commit-management",
                "source_excerpt": {
                    "path": "examples/git-commit-management.yaml",
                    "start_line": 16,
                    "end_line": 20
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.git.commit.create",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.git.commit.amend": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "git_commit_amend_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Amend the current HEAD commit when the workflow intentionally wants history rewriting instead of another follow-up commit.",
                "source_example": "git-commit-management",
                "source_excerpt": {
                    "path": "examples/git-commit-management.yaml",
                    "start_line": 21,
                    "end_line": 25
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.git.commit.amend",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.git.commit.revert": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "git_commit_revert_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Create a compensating revert commit for one target commit while preserving visible history.",
                "source_example": "git-commit-management",
                "source_excerpt": {
                    "path": "examples/git-commit-management.yaml",
                    "start_line": 26,
                    "end_line": 30
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.git.commit.revert",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.git.commits": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "git_commits_probe_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Read a bounded Git commit-history slice when the workflow needs commit texts instead of diffs or a history diagram.",
                "source_example": "git-commit-management",
                "source_excerpt": {
                    "path": "examples/git-commit-management.yaml",
                    "start_line": 10,
                    "end_line": 15
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.git.commits",
                    "expected_status": "ok"
                }
            },
            {
                "name": "git_commit_management_flow",
                "kind": "positive",
                "form": "workflow_fragment",
                "summary": "Inspect recent commit texts, then choose exactly one deliberate history change: create, amend, or revert.",
                "source_example": "git-commit-management",
                "source_excerpt": {
                    "path": "examples/git-commit-management.yaml",
                    "start_line": 1,
                    "end_line": 35
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "workflow_fragment",
                    "target": "connector.git.commits",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.git.tag": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "git_tag_probe_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Inspect one exact Git tag before branching on its existence or publishing its ref and object identity.",
                "source_example": "git-tag-inspection",
                "source_excerpt": {
                    "path": "examples/git-tag-inspection.yaml",
                    "start_line": 8,
                    "end_line": 12
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.git.tag",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.git.tags": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "git_tags_probe_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Inspect a version-sorted Git tag inventory when the workflow needs more than one exact tag lookup.",
                "source_example": "git-tag-inspection",
                "source_excerpt": {
                    "path": "examples/git-tag-inspection.yaml",
                    "start_line": 13,
                    "end_line": 18
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.git.tags",
                    "expected_status": "ok"
                }
            },
            {
                "name": "git_tag_inventory_flow",
                "kind": "positive",
                "form": "workflow_fragment",
                "summary": "Inspect one exact tag and one matching tag inventory together so a workflow can compare single-tag existence with broader release-tag discovery.",
                "source_example": "git-tag-inspection",
                "source_excerpt": {
                    "path": "examples/git-tag-inspection.yaml",
                    "start_line": 1,
                    "end_line": 23
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "workflow_fragment",
                    "target": "connector.git.tags",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.git.ref": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "git_ref_probe_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Inspect one exact Git ref before branching on existence, symbolic-target behavior, or downstream comparison choices.",
                "source_example": "git-ref-range-inspection",
                "source_excerpt": {
                    "path": "examples/git-ref-range-inspection.yaml",
                    "start_line": 10,
                    "end_line": 14
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.git.ref",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.git.range": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "git_range_probe_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Compare two Git revision endpoints when the workflow needs merge-base and ahead/behind facts rather than one exact ref lookup.",
                "source_example": "git-ref-range-inspection",
                "source_excerpt": {
                    "path": "examples/git-ref-range-inspection.yaml",
                    "start_line": 15,
                    "end_line": 19
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.git.range",
                    "expected_status": "ok"
                }
            },
            {
                "name": "git_ref_range_flow",
                "kind": "positive",
                "form": "workflow_fragment",
                "summary": "Inspect one exact ref and one endpoint comparison together so a workflow can separate single-ref validation from ahead/behind relationship facts.",
                "source_example": "git-ref-range-inspection",
                "source_excerpt": {
                    "path": "examples/git-ref-range-inspection.yaml",
                    "start_line": 1,
                    "end_line": 26
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "workflow_fragment",
                    "target": "connector.git.range",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.git.repo": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "git_repo_probe_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Inspect repository-level Git context before making narrower branch, upstream, or worktree decisions.",
                "source_example": "git-repo-upstream-inspection",
                "source_excerpt": {
                    "path": "examples/git-repo-upstream-inspection.yaml",
                    "start_line": 6,
                    "end_line": 8
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.git.repo",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.git.upstream": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "git_upstream_probe_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Inspect the current branch's tracked remote and branch names before deciding whether publication is appropriate.",
                "source_example": "git-repo-upstream-inspection",
                "source_excerpt": {
                    "path": "examples/git-repo-upstream-inspection.yaml",
                    "start_line": 9,
                    "end_line": 11
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.git.upstream",
                    "expected_status": "ok"
                }
            },
            {
                "name": "git_repo_upstream_flow",
                "kind": "positive",
                "form": "workflow_fragment",
                "summary": "Publish repository context and the current branch's tracked remote and branch relationship for a later decision.",
                "source_example": "git-repo-upstream-inspection",
                "source_excerpt": {
                    "path": "examples/git-repo-upstream-inspection.yaml",
                    "start_line": 1,
                    "end_line": 20
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "workflow_fragment",
                    "target": "connector.git.upstream",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.git.index.add_all": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "git_index_add_all_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Stage the whole current Git worktree once the workflow has already decided that every pending change belongs in the next staging batch.",
                "source_example": "git-worktree-staging",
                "source_excerpt": {
                    "path": "examples/git-worktree-staging.yaml",
                    "start_line": 9,
                    "end_line": 11
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.git.index.add_all",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.git.worktree": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "git_worktree_probe_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Inspect the current dirty-path set and worktree cleanliness before staging or other Git mutations depend on those details.",
                "source_example": "git-worktree-staging",
                "source_excerpt": {
                    "path": "examples/git-worktree-staging.yaml",
                    "start_line": 6,
                    "end_line": 8
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.git.worktree",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.git.state": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "git_state_probe_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Inspect one combined Git repository-state snapshot after staging decisions need branch, cleanliness, and stash facts together.",
                "source_example": "git-worktree-staging",
                "source_excerpt": {
                    "path": "examples/git-worktree-staging.yaml",
                    "start_line": 12,
                    "end_line": 14
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.git.state",
                    "expected_status": "ok"
                }
            },
            {
                "name": "git_worktree_staging_flow",
                "kind": "positive",
                "form": "workflow_fragment",
                "summary": "Inspect the dirty worktree, stage the full batch, then read one combined repository-state snapshot so the workflow keeps path-level and summary-level Git checks distinct.",
                "source_example": "git-worktree-staging",
                "source_excerpt": {
                    "path": "examples/git-worktree-staging.yaml",
                    "start_line": 1,
                    "end_line": 21
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "workflow_fragment",
                    "target": "connector.git.state",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.git.integrate.merge": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "git_integrate_merge_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Merge one target ref into the current checkout when the workflow explicitly wants an integration commit instead of a fast-forward-only update.",
                "source_example": "git-integration-strategies",
                "source_excerpt": {
                    "path": "examples/git-integration-strategies.yaml",
                    "start_line": 19,
                    "end_line": 23
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.git.integrate.merge",
                    "expected_status": "ok"
                }
            },
            {
                "name": "git_integration_strategy_flow",
                "kind": "positive",
                "form": "workflow_fragment",
                "summary": "Contrast merge, fast-forward-only merge, cherry-pick, and rebase --onto in one teaching workflow so each Git integration surface keeps its own unit of change and history semantics.",
                "source_example": "git-integration-strategies",
                "source_excerpt": {
                    "path": "examples/git-integration-strategies.yaml",
                    "start_line": 1,
                    "end_line": 45
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "workflow_fragment",
                    "target": "connector.git.integrate.merge",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.git.integrate.merge_ff_only": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "git_integrate_merge_ff_only_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Advance the current checkout to one target ref only when the histories already allow a fast-forward update.",
                "source_example": "git-integration-strategies",
                "source_excerpt": {
                    "path": "examples/git-integration-strategies.yaml",
                    "start_line": 24,
                    "end_line": 28
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.git.integrate.merge_ff_only",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.git.integrate.cherry_pick": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "git_integrate_cherry_pick_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Cherry-pick one chosen commit when the workflow wants a targeted backport-style transplant instead of integrating the whole source ref.",
                "source_example": "git-integration-strategies",
                "source_excerpt": {
                    "path": "examples/git-integration-strategies.yaml",
                    "start_line": 29,
                    "end_line": 33
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.git.integrate.cherry_pick",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.git.integrate.rebase_onto": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "git_integrate_rebase_onto_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Rewrite one topic branch onto a new base when the workflow intentionally wants branch-range replay rather than merge-based integration.",
                "source_example": "git-integration-strategies",
                "source_excerpt": {
                    "path": "examples/git-integration-strategies.yaml",
                    "start_line": 34,
                    "end_line": 40
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.git.integrate.rebase_onto",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.git.sync.fetch": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "git_sync_fetch_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Refresh one explicit configured remote name (origin or team/origin when configured), validated during run before transport, before comparing branch divergence.",
                "source_example": "git-sync-roundtrip",
                "source_excerpt": {
                    "path": "examples/git-sync-roundtrip.yaml",
                    "start_line": 9,
                    "end_line": 12
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.git.sync.fetch",
                    "expected_status": "ok"
                }
            },
            {
                "name": "git_sync_roundtrip_flow",
                "kind": "positive",
                "form": "workflow_fragment",
                "summary": "Fetch from one explicit configured remote name, inspect divergence and upstream context, then push one local branch to that same name; explicit naming keeps the roundtrip target clear.",
                "source_example": "git-sync-roundtrip",
                "source_excerpt": {
                    "path": "examples/git-sync-roundtrip.yaml",
                    "start_line": 1,
                    "end_line": 31
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "workflow_fragment",
                    "target": "connector.git.sync.fetch",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.git.sync.push": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "git_sync_push_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Publish one local branch to an explicit configured remote name after refresh and inspection. Omitted/null remote instead uses the current branch's exact configured upstream remote, including nested names; run validates membership before transport.",
                "source_example": "git-sync-roundtrip",
                "source_excerpt": {
                    "path": "examples/git-sync-roundtrip.yaml",
                    "start_line": 22,
                    "end_line": 26
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.git.sync.push",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.git.stash": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "git_stash_probe_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Inspect the current stash list before later workflow steps decide whether hidden local work needs recovery or acknowledgement.",
                "source_example": "git-stash-inspection",
                "source_excerpt": {
                    "path": "examples/git-stash-inspection.yaml",
                    "start_line": 6,
                    "end_line": 8
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.git.stash",
                    "expected_status": "ok"
                }
            },
            {
                "name": "git_stash_inspection_flow",
                "kind": "positive",
                "form": "workflow_fragment",
                "summary": "Inspect stash inventory alongside repository state so workflows can distinguish saved stash entries from current dirty-worktree facts.",
                "source_example": "git-stash-inspection",
                "source_excerpt": {
                    "path": "examples/git-stash-inspection.yaml",
                    "start_line": 1,
                    "end_line": 15
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "workflow_fragment",
                    "target": "connector.git.stash",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.git.worktrees": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "git_worktrees_probe_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Inspect the repository-wide worktree inventory before later steps reason about current versus sibling checkouts.",
                "source_example": "git-worktree-inventory",
                "source_excerpt": {
                    "path": "examples/git-worktree-inventory.yaml",
                    "start_line": 9,
                    "end_line": 11
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.git.worktrees",
                    "expected_status": "ok"
                }
            },
            {
                "name": "git_worktree_inventory_flow",
                "kind": "positive",
                "form": "workflow_fragment",
                "summary": "Inspect repository worktrees together with current-worktree cleanliness so the workflow can distinguish repository-wide topology from local dirty-state details.",
                "source_example": "git-worktree-inventory",
                "source_excerpt": {
                    "path": "examples/git-worktree-inventory.yaml",
                    "start_line": 1,
                    "end_line": 24
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "workflow_fragment",
                    "target": "connector.git.worktrees",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.shell.command": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "shell_command_legacy_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Run one explicit legacy shell command step when the workflow is documenting or containing compatibility behavior rather than teaching shell.command as a preferred new design.",
                "source_example": "shell-command-legacy-compatibility",
                "source_excerpt": {
                    "path": "examples/shell-command-legacy-compatibility.yaml",
                    "start_line": 6,
                    "end_line": 10
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "connector.shell.command",
                    "expected_status": "ok"
                }
            },
            {
                "name": "shell_command_legacy_workflow",
                "kind": "positive",
                "form": "workflow_fragment",
                "summary": "Show shell.command only inside an explicitly legacy compatibility workflow so the published example teaches containment and caution rather than endorsement.",
                "source_example": "shell-command-legacy-compatibility",
                "source_excerpt": {
                    "path": "examples/shell-command-legacy-compatibility.yaml",
                    "start_line": 1,
                    "end_line": 16
                },
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "workflow_fragment",
                    "target": "connector.shell.command",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "connector.gh.issue": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "gh_issue_probe_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Inspect one GitHub issue and register the typed snapshot for later workflow decisions.",
                "source_example": "examples.gh-issue-maintenance",
                "source_excerpt": {
                    "path": "examples/gh-issue-maintenance.yaml",
                    "start_line": 17,
                    "end_line": 22
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.gh-issue-maintenance"
                },
            },
            {
                "name": "gh_issue_full_maintenance_flow",
                "kind": "positive",
                "form": "workflow_fragment",
                "summary": "Create an issue, inspect it, comment on it, edit the body, inspect comments, and close it with typed GitHub issue operations.",
                "source_example": "examples.gh-issue-maintenance",
                "source_excerpt": {
                    "path": "examples/gh-issue-maintenance.yaml",
                    "start_line": 1,
                    "end_line": 56
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.gh-issue-maintenance"
                },
            }
        ],
    },
    "connector.gh.issue.create": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "gh_issue_create_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Create one new GitHub issue and register its returned reference for later steps.",
                "source_example": "examples.gh-issue-maintenance",
                "source_excerpt": {
                    "path": "examples/gh-issue-maintenance.yaml",
                    "start_line": 10,
                    "end_line": 16
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.gh-issue-maintenance"
                },
            }
        ],
    },
    "connector.gh.issue.close": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "gh_issue_close_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Close one existing GitHub issue after earlier workflow steps have already selected the target issue number.",
                "source_example": "examples.gh-issue-maintenance",
                "source_excerpt": {
                    "path": "examples/gh-issue-maintenance.yaml",
                    "start_line": 52,
                    "end_line": 56
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.gh-issue-maintenance"
                },
            }
        ],
    },
    "connector.gh.issue.comments": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "gh_issue_comments_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Inspect the issue comment thread with one explicit limit and register the resulting comment snapshot.",
                "source_example": "examples.gh-issue-maintenance",
                "source_excerpt": {
                    "path": "examples/gh-issue-maintenance.yaml",
                    "start_line": 45,
                    "end_line": 51
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.gh-issue-maintenance"
                },
            }
        ],
    },
    "connector.gh.issue.comment.add": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "gh_issue_comment_add_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Add one human-facing follow-up comment to the issue conversation without rewriting the issue body.",
                "source_example": "examples.gh-issue-maintenance",
                "source_excerpt": {
                    "path": "examples/gh-issue-maintenance.yaml",
                    "start_line": 23,
                    "end_line": 28
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.gh-issue-maintenance"
                },
            }
        ],
    },
    "connector.gh.issue.body.append": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "gh_issue_body_append_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Append one extra note to the existing issue body while preserving earlier body content.",
                "source_example": "examples.gh-issue-maintenance",
                "source_excerpt": {
                    "path": "examples/gh-issue-maintenance.yaml",
                    "start_line": 29,
                    "end_line": 35
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.gh-issue-maintenance"
                },
            }
        ],
    },
    "connector.gh.issue.body.replace": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "gh_issue_body_replace_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Rewrite the full issue body when the workflow owns the canonical issue description.",
                "source_example": "examples.gh-issue-maintenance",
                "source_excerpt": {
                    "path": "examples/gh-issue-maintenance.yaml",
                    "start_line": 36,
                    "end_line": 44
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.gh-issue-maintenance"
                },
            }
        ],
    },
    "connector.gh.pr": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "gh_pr_probe_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Inspect one pull request headline snapshot before branching into narrower diff, review, comment, and checks surfaces.",
                "source_example": "examples.inspect-pr",
                "source_excerpt": {
                    "path": "examples/inspect-pr.yaml",
                    "start_line": 8,
                    "end_line": 13
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.inspect-pr"
                },
            },
            {
                "name": "gh_pr_full_inspection_flow",
                "kind": "positive",
                "form": "workflow_fragment",
                "summary": "Inspect one pull request through metadata, diff, comments, reviews, review comments, checks, and timeline surfaces, then publish a digest.",
                "source_example": "examples.inspect-pr",
                "source_excerpt": {
                    "path": "examples/inspect-pr.yaml",
                    "start_line": 1,
                    "end_line": 70
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.inspect-pr"
                },
            }
        ],
    },
    "connector.gh.pr.diff": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "gh_pr_diff_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Inspect changed files and bounded diff content from one pull request before reacting to code-level changes.",
                "source_example": "examples.inspect-pr",
                "source_excerpt": {
                    "path": "examples/inspect-pr.yaml",
                    "start_line": 14,
                    "end_line": 20
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.inspect-pr"
                },
            }
        ],
    },
    "connector.gh.pr.comments": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "gh_pr_comments_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Inspect the top-level pull request conversation thread with one explicit limit and register the resulting comment list.",
                "source_example": "examples.inspect-pr",
                "source_excerpt": {
                    "path": "examples/inspect-pr.yaml",
                    "start_line": 21,
                    "end_line": 27
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.inspect-pr"
                },
            }
        ],
    },
    "connector.gh.pr.reviews": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "gh_pr_reviews_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Inspect submitted pull-request reviews with one explicit limit before interpreting approval or change-request history.",
                "source_example": "examples.inspect-pr",
                "source_excerpt": {
                    "path": "examples/inspect-pr.yaml",
                    "start_line": 28,
                    "end_line": 34
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.inspect-pr"
                },
            }
        ],
    },
    "connector.gh.pr.review_comments": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "gh_pr_review_comments_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Inspect line-level review comments with one explicit limit when the workflow needs file-anchored reviewer feedback.",
                "source_example": "examples.inspect-pr",
                "source_excerpt": {
                    "path": "examples/inspect-pr.yaml",
                    "start_line": 35,
                    "end_line": 41
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.inspect-pr"
                },
            }
        ],
    },
    "connector.gh.pr.checks": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "gh_pr_checks_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Inspect status contexts and check runs for the pull request head before merge-readiness decisions.",
                "source_example": "examples.inspect-pr",
                "source_excerpt": {
                    "path": "examples/inspect-pr.yaml",
                    "start_line": 42,
                    "end_line": 47
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.inspect-pr"
                },
            }
        ],
    },
    "connector.gh.pr.timeline": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "gh_pr_timeline_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Inspect lifecycle events from the pull request timeline with one explicit limit before summarizing history.",
                "source_example": "examples.inspect-pr",
                "source_excerpt": {
                    "path": "examples/inspect-pr.yaml",
                    "start_line": 48,
                    "end_line": 54
                },
                "verification": {
                    "kind": "excerpt_verified",
                    "example": "examples.inspect-pr"
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
                "summary": "Show the existing binding example with a read in the mutation payload. Excerpt verification checks source fidelity only, not bound file identity, profile contexts, or persistence; distinct roles do not guarantee distinct files.",
                "source_example": "examples.state-bindings",
                "source_excerpt": {
                    "path": "examples/state-bindings.yaml",
                    "start_line": 1,
                    "end_line": 15
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
    "workflow.step_forms.result": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "result_form_minimal_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Use the dedicated result step form when one named step appends one final value to the workflow result list.",
                "yaml": '- name: emit-result\n  result:\n    status: "ok"\n    summary: "Workflow prepared"',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "workflow.step_forms.result",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "workflow.step_forms.publish": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "publish_form_minimal_step",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Use the dedicated publish step form when one named step emits an outward-facing published payload for callers.",
                "yaml": '- name: publish-summary\n  publish:\n    summary: "Workflow prepared"\n    ready: true',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "workflow.step_forms.publish",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "workflow.step.gate": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "step_gate_value_requires_issue_number",
                "kind": "positive",
                "form": "value",
                "summary": "Show a valid `workflow.step.gate` value for admitting a step only when one required input is present.",
                "yaml": "is_present(inputs.issue_number)",
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_field",
                    "target": "workflow.step.gate",
                    "expected_status": "ok"
                }
            },
            {
                "name": "step_gate_checkpoint_fragment",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Show one complete gate-checkpoint step that blocks later work unless the required issue number is present.",
                "yaml": "- name: verify-issue-context\n  gate: is_present(inputs.issue_number)",
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "workflow.step.gate",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "workflow.step.result": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "step_result_value_payload",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Show a valid `workflow.step.result` payload for appending one final result value to the workflow result list.",
                "yaml": 'result:\n  status: "ok"\n  summary: "Workflow prepared"',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_field",
                    "target": "workflow.step.result",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "workflow.step.run": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "step_run_named_target_value",
                "kind": "positive",
                "form": "value",
                "summary": "Show a valid `workflow.step.run` value for selecting one named reusable runtime target.",
                "yaml": '"fragments/review_issue.yaml"',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_field",
                    "target": "workflow.step.run",
                    "expected_status": "ok"
                }
            },
            {
                "name": "step_run_named_target_fragment",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Show one complete run-invocation step that calls a named runtime target with explicit argument binding.",
                "yaml": '- name: review-each-issue\n  run: "fragments/review_issue.yaml"\n  with:\n    issue_number: item\n  for_each: inputs.issue_numbers',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "workflow.step.run",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "workflow.step.steps": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "step_steps_inline_body_fragment",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Show a valid `workflow.step.steps` inline repeated body for one short local repeated action.",
                "yaml": 'steps:\n  - name: publish-item\n    publish:\n      issue_number: item',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_field",
                    "target": "workflow.step.steps",
                    "expected_status": "ok"
                }
            },
            {
                "name": "step_steps_inline_fan_out_fragment",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Show one complete inline fan-out step that repeats one short local body for each issue number.",
                "yaml": '- name: publish-each-issue\n  for_each: inputs.issue_numbers\n  steps:\n    - name: publish-item\n      publish:\n        issue_number: item',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "workflow.step.steps",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "workflow.step.for_each": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "step_for_each_array_source_value",
                "kind": "positive",
                "form": "value",
                "summary": "Show a valid `workflow.step.for_each` value for one array-valued repeated item source.",
                "yaml": "inputs.issue_numbers",
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_field",
                    "target": "workflow.step.for_each",
                    "expected_status": "ok"
                }
            },
            {
                "name": "step_for_each_inline_fan_out_fragment",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Show one complete inline repeated step that binds an array source through for_each before running a short local body.",
                "yaml": '- name: publish-each-issue\n  for_each: inputs.issue_numbers\n  steps:\n    - name: publish-item\n      publish:\n        issue_number: item',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "workflow.step.for_each",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "workflow.step.with": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "step_with_argument_mapping_fragment",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Show a valid `workflow.step.with` mapping for binding runtime arguments into a named run target.",
                "yaml": 'with:\n  issue_number: item\n  review_mode: inputs.review_mode',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_field",
                    "target": "workflow.step.with",
                    "expected_status": "ok"
                }
            },
            {
                "name": "step_with_run_invocation_fragment",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Show one complete run-invocation step that binds explicit runtime arguments through with.",
                "yaml": '- name: review-each-issue\n  run: "fragments/review_issue.yaml"\n  with:\n    issue_number: item\n    review_mode: inputs.review_mode\n  for_each: inputs.issue_numbers',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "workflow.step.with",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "workflow.step.uses": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "step_uses_operation_value",
                "kind": "positive",
                "form": "value",
                "summary": "Show a valid `workflow.step.uses` value for selecting one published operation surface.",
                "yaml": '"git.repo"',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_field",
                    "target": "workflow.step.uses",
                    "expected_status": "ok"
                }
            },
            {
                "name": "step_uses_operation_fragment",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Show one complete operation-call step that selects a published operation and registers its result for later reuse.",
                "yaml": '- name: inspect-repository\n  uses: "git.repo"\n  register: repo_info',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "workflow.step.uses",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "workflow.step.register": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "step_register_binding_value",
                "kind": "positive",
                "form": "value",
                "summary": "Show a valid `workflow.step.register` value for binding one step result to a reusable local name.",
                "yaml": "repo_info",
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_field",
                    "target": "workflow.step.register",
                    "expected_status": "ok"
                }
            },
            {
                "name": "step_register_value_fragment",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Show one complete value step that stages reusable local dataflow through register.",
                "yaml": '- name: classify-status\n  value: inputs.status | in(inputs.allowed)\n  register: status_allowed',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_fragment",
                    "target": "workflow.step.register",
                    "expected_status": "ok"
                }
            }
        ],
    },
    "workflow.step.publish": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "step_publish_value_payload",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Show a valid `workflow.step.publish` payload for emitting one outward-facing published output bundle.",
                "yaml": 'publish:\n  summary: "Workflow prepared"\n  ready: true',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_field",
                    "target": "workflow.step.publish",
                    "expected_status": "ok"
                }
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
                "summary": "Persist a fixed value with the input used only to select the state key.",
                "yaml": 'state_set:\n  state.task_memory[inputs.task_key].issue_number: 42',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "step_field",
                    "target": "workflow.step.state_set",
                    "expected_status": "ok",
                },
            },
            {
                "name": "state_set_step_fragment_remembers_profile",
                "kind": "positive",
                "form": "step_fragment",
                "summary": "Read the previously stored profile before replacing it, then reuse the registered value in the result for this run.",
                "yaml": '- name: read-profile\n  value: state.shared_state["active_profile"]\n  register: previous_profile\n- name: remember-profile\n  state_set:\n    state.shared_state["active_profile"]: review\n- name: report-previous-profile\n  publish:\n    previous_profile: step.previous_profile.outputs.value',
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
                "summary": "Read the remembered branch before deleting it for future runs, then publish the registered value without rereading the file through any role. Verification checks unbound authored order only, not bound file identity, profile contexts, or persistence.",
                "yaml": '- name: read-branch\n  value: state.task_memory[inputs.issue_ref].branch\n  register: previous_branch\n- name: forget-branch\n  state_delete: state.task_memory[inputs.issue_ref].branch\n- name: report-previous-branch\n  publish:\n    previous_branch: step.previous_branch.outputs.value',
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
    "workflow.local_expression.filter.catch": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "catch_issue_not_found_with_false_fallback",
                "kind": "positive",
                "form": "value",
                "summary": "Turn one expected missing-issue failure into an explicit false fallback value.",
                "yaml": 'gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).body | catch(["issue_not_found"], false)',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "expression_value",
                    "target": "workflow.local_expression.filter.catch",
                    "expected_status": "ok",
                },
            }
        ],
    },
    "workflow.local_expression.filter.not_found": {
        "snippet_coverage": "runner_verified",
        "canonical_examples": [
            {
                "name": "not_found_boolean_probe_verdict",
                "kind": "positive",
                "form": "value",
                "summary": "Turn one strict probe lookup into a boolean absence check for conditional routing.",
                "yaml": 'gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).body | not_found',
                "verification": {
                    "kind": "runner_verified",
                    "world": "default",
                    "insertion_mode": "expression_value",
                    "target": "workflow.local_expression.filter.not_found",
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
                "name": "adapter_json_value_binding",
                "kind": "positive",
                "form": "value",
                "summary": "Read one JSON value by explicitly supplying the workflow input that contains the JSON text.",
                "yaml": "'${json.user.name with{root: inputs.body}}'",
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
                "name": "Complete routine registry and helper",
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

# The routine contract guide is the authoring entry point, so show the complete
# checked bundle there rather than making a new author discover it indirectly.
HELP_SNIPPET_REGISTRY["routine_contract"] = {
    "snippet_coverage": "runner_verified",
    "canonical_examples": [deepcopy(HELP_SNIPPET_REGISTRY["routine"]["canonical_examples"][3])],
}


for _family, _leaf, _name, _summary in (
    (
        "connector.fs", "connector.fs.file", "fs_family_file_observation",
        "Supply the required file_path with no real-file default. The fs.file probe observes UTF-8 content and metadata; publish returns basename, byte size, line count, and content-derived character count without publishing full content. Relative and absolute paths remain textual projections; parent symlinks and hardlinks are allowed, not workspace confinement or atomic snapshots.",
    ),
    (
        "connector.gh", "connector.gh.project.issue", "gh_family_project_membership",
        "Supply repository as literal ASCII OWNER/REPO, issue_number, and project_id. The gh.project.issue probe reads membership; gh.project.issue.add conditionally attaches the issue, then the number, iteration, and single-select setters mutate project fields. These actions are not read-only probes, and earlier effects are not rolled back if a later action fails. Context is a default rather than an authorization allowlist; an explicit valid other repository remains allowed with a warning.",
    ),
):
    _example = deepcopy(next(
        example for example in HELP_SNIPPET_REGISTRY[_leaf]["canonical_examples"]
        if example["form"] == "workflow_fragment"
    ))
    _example.update(name=_name, summary=_summary)
    HELP_SNIPPET_REGISTRY[_family] = {
        "snippet_coverage": _example["verification"]["kind"],
        "canonical_examples": [_example],
    }


STATE_BUNDLE_EXAMPLES = [
    {
        "name": "bound_state_independent_guard_after_mutations",
        "kind": "positive",
        "form": "state_bundle",
        "summary": "Bind two roles to one world file, read before mutations, then check an independent input guard. Top-level preflight defers the writes without simulating them; execution retains their order. This bundle verifies bound validity only, not check output or execution.",
        "yaml": '''state_bindings:
  shared_state: shared_state
  alias: shared_state
expected_diagnostic_codes: []
workflow_text: |
  version: 0
  workflow: remember-profile
  inputs:
    ship: {default: true}
  state_needs:
    shared_state: {}
    alias: {}
  blocks:
    - steps:
        - name: read-profile
          value: state.alias["active_profile"]
          register: previous_profile
        - name: remember-profile
          state_set:
            state.shared_state["active_profile"]: review
        - name: forget-publish-flag
          state_delete: state.shared_state["should_publish_summary"]
        - name: report-previous-profile
          publish:
            previous_profile: step.previous_profile.outputs.value
    - guards:
        - inputs.ship == true''',
        "verification": {
            "kind": "runner_verified", "world": "default", "insertion_mode": "state_bundle",
            "target": "state", "expected_status": "ok",
        },
    },
    {
        "name": "bound_state_alias_read_after_write_rejected",
        "kind": "negative",
        "form": "state_bundle",
        "summary": "Rejected: a different role and key still read the same actual file after mutation. The bundle verifies the exact bound-storage diagnostic, without executing a write or reading state contents.",
        "yaml": '''state_bindings:
  shared_state: shared_state
  alias: shared_state
expected_diagnostic_codes:
  - validation.workflow.state_storage.write_before_last_read
workflow_text: |
  version: 0
  workflow: invalid-alias-order
  state_needs:
    shared_state: {}
    alias: {}
  blocks:
    - steps:
        - name: forget-profile
          state_delete: state.shared_state["active_profile"]
        - name: read-alias
          value: state.alias["should_publish_summary"]''',
        "verification": {
            "kind": "runner_verified", "world": "default", "insertion_mode": "state_bundle",
            "target": "state", "expected_status": "validation_error",
        },
    },
]

GRAPH_BUNDLE_EXAMPLE = {
    "name": "static_graph_bridge_and_reset",
    "kind": "positive", "form": "graph_bundle",
    "summary": "A writing data user nests below its source; a join follows the established source chain with an extra source reference. Fallback reads remain links, with reads from: bridge? separate from conditional mutation effects. Terminal deletion ends the related section. Exact links, loops and text are verified without executing workflows.",
    "yaml": '''workflows:
  - |
    version: 0
    workflow: open
    state_needs:
      shared_state: {}
    blocks:
      - steps:
          - name: remember
            state_set:
              state.shared_state["repo"].issue: 1
  - |
    version: 0
    workflow: bridge
    inputs:
      enabled: {default: true}
    state_needs:
      shared_state: {}
    blocks:
      - steps:
          - name: read-issue
            value: state.shared_state["repo"].issue
            register: issue
          - name: remember-branch
            if: inputs.enabled
            state_set:
              state.shared_state["repo"].branch: "work"
          - name: remember-token
            if: inputs.enabled
            state_set:
              state.shared_state["repo"].token: "saved"
  - |
    version: 0
    workflow: reset
    state_needs:
      shared_state: {}
    blocks:
      - steps:
          - name: read-issue
            value: state.shared_state["repo"].issue
          - name: read-branch
            value: state.shared_state["repo"].branch
          - name: forget
            state_delete: state.shared_state["repo"]
  - |
    version: 0
    workflow: z-observer
    state_needs:
      shared_state: {}
    blocks:
      - steps:
          - name: use-issue
            value: state.shared_state["repo"].issue
  - |
    version: 0
    workflow: observer
    state_needs:
      shared_state: {}
    blocks:
      - steps:
          - name: use-issue
            value: state.shared_state["repo"].issue
  - |
    version: 0
    workflow: joined-user
    state_needs:
      shared_state: {}
    blocks:
      - steps:
          - name: use-issue
            value: state.shared_state["repo"].issue
          - name: optional-branch
            value: state.shared_state["repo"].branch | catch(["runtime.value.state_missing"], null)
expected_links:
  - [open, bridge, handoff, proven]
  - [open, reset, handoff, proven]
  - [bridge, reset, handoff, proven]
  - [reset, bridge, invalidation, proven]
  - [open, observer, handoff, proven]
  - [reset, observer, invalidation, proven]
  - [open, joined-user, handoff, proven]
  - [bridge, joined-user, handoff, proven]
  - [reset, joined-user, invalidation, proven]
  - [open, z-observer, handoff, proven]
  - [reset, z-observer, invalidation, proven]
expected_loops:
  - [bridge, reset]
expected_text: |
  Shared context: writers → readers, not execution order.
  + write, − delete, ? conditional.

  open (+issue)
  ├── bridge (+branch?, +token?)
  │   ├── joined-user [also reads from: open; reads from: bridge?]
  │   └── reset (−context) [also reads from: open]
  ├── z-observer
  └── observer

  Details: --json.
  Full list: ordo-playbook workflows list''',
    "verification": {"kind": "runner_verified", "world": "default", "insertion_mode": "graph_bundle",
                     "target": "state", "expected_status": "ok"},
}
HELP_SNIPPET_REGISTRY["command-line.ordo-playbook"] = {
    "snippet_coverage": "none", "canonical_examples": []}

GRAPH_PROFILE_EXAMPLE = {
    "name": "static_profiles_and_bootstrap_provenance", "kind": "positive", "form": "graph_bundle",
    "summary": "Load a real static playbook bundle without state contents. A literal profile switch preserves the protected selector default; bootstrap reads retain detailed links but do not attach the bootstrap-only workflow to the business tree. No probes or effects execute.",
    "yaml": '''playbook_text: |
  version: 1
  defaults: {profile: fixed}
  profiles:
    fixed: {file: ./fixed.yaml}
  states:
    env: {path: ./env.json}
  pre_run:
    - file: ./bootstrap.yaml
      state_bindings: {env: env}
  workflows:
    remember:
      file: ./remember.yaml
      state_bindings: {env: env}
    inspect:
      file: ./inspect.yaml
      state_bindings: {env: env}
    bootstrap-only:
      file: ./empty.yaml
files:
  fixed.yaml: |
    name: fixed
    inputs: {repository: repo}
  bootstrap.yaml: |
    version: 0
    workflow: bootstrap
    inputs:
      selector: {default: selected}
    state_needs: {env: {}}
    let:
      chosen: state.env[inputs.selector]
    blocks:
      - steps:
          - name: switch
            profile_switch: ${chosen}
  remember.yaml: |
    version: 0
    workflow: remember
    inputs:
      selector: {default: selected}
    state_needs: {env: {}}
    blocks:
      - steps:
          - name: fixed-profile
            profile_switch: "fixed"
          - name: remember
            state_set:
              state.env[inputs.selector]: "fixed"
              state.env["issue"]: 1
  inspect.yaml: |
    version: 0
    workflow: inspect
    state_needs: {env: {}}
    blocks:
      - steps:
          - name: read
            value: state.env["issue"]
  empty.yaml: |
    version: 0
    workflow: bootstrap-only
    blocks: []
expected_links:
  - [remember, inspect, handoff, proven]
  - [remember, bootstrap-only, handoff, proven]
expected_loops: []
expected_text: |
  Shared context: writers → readers, not execution order.
  + write, − delete, ? conditional.

  remember (+env["selected"], +env["issue"])
  └── inspect

  Bootstrap dependencies: --json.

  Details: --json.
  Full list: ordo-playbook workflows list''',
    "verification": {"kind": "runner_verified", "world": "default", "insertion_mode": "graph_bundle",
                     "target": "state", "expected_status": "ok"},
}
GRAPH_PARAMETER_EXAMPLE = {
    "name": "state_family_parameter_correspondence", "kind": "positive", "form": "graph_bundle",
    "summary": "Verify a profile-indexed state family without selecting or reading state. The concrete handoff remains possible, while the separate structural link carries shared-origin correspondence and a selector equality requirement. The default tree displays the producer/reader family, not a concrete address or execution guarantee.",
    "yaml": '''playbook_text: |
  version: 1
  defaults: {profile: alpha}
  profiles:
    alpha: {file: ./alpha.yaml}
    beta: {file: ./beta.yaml}
  states:
    data: {path: ./state.json}
    env: {path: ./env.json}
  pre_run:
    - file: ./bootstrap.yaml
      state_bindings: {env: env}
  workflows:
    producer:
      file: ./producer.yaml
      state_bindings: {data: data}
    reader:
      file: ./reader.yaml
      state_bindings: {data: data}
files:
  alpha.yaml: |
    name: alpha
    inputs: {repository: org/alpha}
    working_directory: /structural/alpha
  beta.yaml: |
    name: beta
    inputs: {repository: org/beta}
    working_directory: /structural/beta
  bootstrap.yaml: |
    version: 0
    workflow: bootstrap
    state_needs: {env: {}}
    blocks:
      - steps:
          - name: choose-profile
            profile_switch: state.env["selected"]
  producer.yaml: |
    version: 0
    workflow: producer
    inputs: {repository: {}}
    state_needs: {data: {}}
    blocks:
      - steps:
          - name: remember
            state_set:
              state.data[inputs.repository].issue: 1
              state.data[inputs.repository].branch: "work"
  reader.yaml: |
    version: 0
    workflow: reader
    inputs: {repository: {}}
    state_needs: {data: {}}
    blocks:
      - steps:
          - name: use-context
            value:
              issue: state.data[inputs.repository].issue
              branch: state.data[inputs.repository].branch
expected_links:
  - [producer, reader, handoff, possible]
expected_loops: []
expected_structural_links:
  - from: producer
    to: reader
    kind: handoff
    correspondence: shared_origin_parameter
    requires: [selector_equal]
expected_text: |
  Shared context: writers → readers, not execution order.
  + write, − delete, ? conditional.

  producer (+issue, +branch)
  └── reader

  Bootstrap dependencies: --json.

  Parametric links require matching selectors, state instances and read shapes.

  Details: --json.
  Full list: ordo-playbook workflows list''',
    "verification": {"kind": "runner_verified", "world": "default", "insertion_mode": "graph_bundle",
                     "target": "state", "expected_status": "ok"},
}
GRAPH_ALTERNATIVES_EXAMPLE = {
    "name": "alternatives_do_not_select_a_parent", "kind": "positive", "form": "graph_bundle",
    "summary": "Verify alternatives as a standalone row with both source references. Unique data use stays nested and the deletion ends its related section. Free roots retain authored order; categories create no dependencies.",
    "yaml": '''playbook_text: |
  version: 1
  states:
    memory: {path: ./memory.json}
  workflows:
    producer:
      file: ./producer.yaml
      category: context
      state_bindings: {memory: memory}
    alternate:
      file: ./alternate.yaml
      category: context
      state_bindings: {memory: memory}
    ready:
      file: ./ready.yaml
      category: lifecycle
      state_bindings: {memory: memory}
    review:
      file: ./review.yaml
      category: lifecycle
      state_bindings: {memory: memory}
    done:
      file: ./done.yaml
      category: lifecycle
      state_bindings: {memory: memory}
files:
  producer.yaml: |
    version: 0
    workflow: producer
    state_needs: {memory: {}}
    blocks:
      - steps:
          - name: write
            state_set:
              state.memory["repo"].choice: true
              state.memory["repo"].story: true
  alternate.yaml: |
    version: 0
    workflow: alternate
    state_needs: {memory: {}}
    blocks:
      - steps:
          - name: write
            state_set:
              state.memory["repo"].choice: true
  ready.yaml: |
    version: 0
    workflow: ready
    state_needs: {memory: {}}
    blocks:
      - steps:
          - name: read
            value: state.memory["repo"].choice
  review.yaml: |
    version: 0
    workflow: review
    state_needs: {memory: {}}
    blocks:
      - steps:
          - name: read
            value: state.memory["repo"].story
  done.yaml: |
    version: 0
    workflow: done
    state_needs: {memory: {}}
    blocks:
      - steps:
          - name: delete
            state_delete: state.memory["repo"].story
expected_links:
  - [producer, ready, handoff, proven]
  - [producer, review, handoff, proven]
  - [alternate, ready, handoff, proven]
  - [done, review, invalidation, proven]
expected_loops: []
expected_text: |
  Shared context: writers → readers, not execution order.
  + write, − delete, ? conditional.

  producer (+choice, +story)
  ├── review
  └── done (−story)
  alternate (+choice)
  ready (data use; alternative sources) [read sources: producer, alternate]

  Details: --json.
  Full list: ordo-playbook workflows list''',
    "verification": {"kind": "runner_verified", "world": "default", "insertion_mode": "graph_bundle",
                     "target": "state", "expected_status": "ok"},
}
GRAPH_ROLES_EXAMPLE = {
    "name": "state_mutation_roles_keep_one_workflow", "kind": "positive", "form": "graph_bundle",
    "summary": "A mutating data user nests beneath its source. One mixed workflow has a terminal deletion role beneath the affected creator and an unsourced write role at root level. Both roles reference one workflow; fields and keys do not create additional logical states.",
    "yaml": '''playbook_text: |
  version: 1
  states:
    memory: {path: ./memory.json}
  workflows:
    creator: {file: ./creator.yaml, state_bindings: {s: memory}}
    reader: {file: ./reader.yaml, state_bindings: {s: memory}}
    other: {file: ./other.yaml, state_bindings: {s: memory}}
    finish: {file: ./finish.yaml, state_bindings: {s: memory}}
files:
  creator.yaml: |
    version: 0
    workflow: creator
    state_needs: {s: {}}
    blocks:
      - steps:
          - name: write
            state_set:
              state.s["repo"].task: true
  reader.yaml: |
    version: 0
    workflow: reader
    state_needs: {s: {}}
    blocks:
      - steps:
          - name: read
            value: state.s["repo"].task
  other.yaml: |
    version: 0
    workflow: other
    state_needs: {s: {}}
    blocks:
      - steps:
          - name: read
            value: state.s["repo"].task
          - name: write
            state_set:
              state.s["repo"].story: true
  finish.yaml: |
    version: 0
    workflow: finish
    state_needs: {s: {}}
    blocks:
      - steps:
          - name: delete
            state_delete: state.s["repo"].task
          - name: write
            state_set:
              state.s["repo"].done: true
expected_links:
  - [creator, reader, handoff, proven]
  - [creator, other, handoff, proven]
  - [finish, reader, invalidation, proven]
  - [finish, other, invalidation, proven]
expected_loops: []
expected_text: |
  Shared context: writers → readers, not execution order.
  + write, − delete, ? conditional.
  ↔ another role of the same workflow.

  creator (+task)
  ├── reader
  ├── other (+story)
  └── finish (−task) ↔ memory/delete
  finish (+done) ↔ memory/write

  Details: --json.
  Full list: ordo-playbook workflows list''',
    "verification": {"kind": "runner_verified", "world": "default", "insertion_mode": "graph_bundle",
                     "target": "state", "expected_status": "ok"},
}
GRAPH_READING_EXAMPLE = {
    "name": "read_a_state_graph", "kind": "positive", "form": "graph_bundle",
    "display": "verified_graph_output",
    "summary": "inspect uses item from remember and category from label. It appears under both sources, but the reference leaf is the same operation, not another execution. Its fallback category read remains data use. forget removes item. This output is verified; JSON includes the source workflows.",
    "yaml": '''workflows:
  - |
    version: 0
    workflow: remember
    state_needs: {shared_state: {}}
    blocks:
      - steps:
          - name: save
            state_set:
              state.shared_state["repo"].item: 1
  - |
    version: 0
    workflow: label
    state_needs: {shared_state: {}}
    blocks:
      - steps:
          - name: save-category
            state_set:
              state.shared_state["repo"].category: "work"
  - |
    version: 0
    workflow: inspect
    state_needs: {shared_state: {}}
    blocks:
      - steps:
          - name: read
            value: state.shared_state["repo"].item
          - name: category
            value: state.shared_state["repo"].category | catch(["runtime.value.state_missing"], null)
  - |
    version: 0
    workflow: forget
    state_needs: {shared_state: {}}
    blocks:
      - steps:
          - name: remove
            state_delete: state.shared_state["repo"].item
expected_links:
  - [remember, inspect, handoff, proven]
  - [label, inspect, handoff, proven]
  - [forget, inspect, invalidation, proven]
expected_loops: []
expected_text: |
  Shared context: writers → readers, not execution order.
  + write, − delete, ? conditional.
  ↔ (reference) the same operation, shown again.

  remember (+item)
  ├── inspect [also reads from: label?]
  └── forget (−item)
  label (+category)
  └── inspect ↔ (reference) [conditional use]

  Details: --json.
  Full list: ordo-playbook workflows list''',
    "verification": {"kind": "runner_verified", "world": "default", "insertion_mode": "graph_bundle",
                     "target": "command-line.ordo-playbook", "expected_status": "ok"},
}
for _state_handle in ("workflow.state_bindings", "workflow.step.state_delete"):
    HELP_SNIPPET_REGISTRY[_state_handle]["snippet_coverage"] = "runner_verified"
    HELP_SNIPPET_REGISTRY[_state_handle]["canonical_examples"].extend(deepcopy(STATE_BUNDLE_EXAMPLES))


def _gh_pr_list_workflow() -> str:
    """One observer document, executed verbatim in every list fixture world."""
    return '''version: 0
workflow: classify-branch-pull-requests
# The explicit repository keeps the target visible in this example.
inputs:
  repository:
    description: Target OWNER/REPO repository.
  head:
    description: Source branch name, without an owner prefix.
  head_owner:
    description: Source owner login (not a repository identity).
  head_repository:
    description: Exact source OWNER/REPO; one owner may have multiple forks.
  base:
    description: Target branch name.
blocks:
  - steps:
      - name: list-candidates
        uses: gh.pr.list
        with:
          repository: inputs.repository
          head: inputs.head
          head_owner: inputs.head_owner
          base: inputs.base
          state: 'all'
        register: candidates
      - name: require-complete-known-identity
        gate:
          all:
            - step.candidates.outputs.complete | eq(true)
            - step.candidates.outputs.items | length | eq(step.candidates.outputs.count)
            - step.candidates.outputs.items | only(head_repository=null) | length | eq(0)
            - step.candidates.outputs.items | only(head_repository="") | length | eq(0)
            - step.candidates.outputs.items | only(head_repository_key!=null) | only(head_repository_key!="") | length | eq(step.candidates.outputs.count)
            - step.candidates.outputs.items | only(head_owner=null) | length | eq(0)
            - step.candidates.outputs.items | only(head_owner="") | length | eq(0)
            - step.candidates.outputs.items | only(head_ref=null) | length | eq(0)
            - step.candidates.outputs.items | only(head_ref="") | length | eq(0)
            - step.candidates.outputs.items | only(base_repository=null) | length | eq(0)
            - step.candidates.outputs.items | only(base_ref=null) | length | eq(0)
      - name: select-exact-source-repository
        value: step.candidates.outputs.items | only(head_repository_key=inputs.head_repository | lower)
        register: exact
      - name: publish-observation
        publish:
          count: step.exact.outputs.value | length
          open: step.exact.outputs.value | only(state="open") | length
          closed: step.exact.outputs.value | only(state="closed") | length
          merged: step.exact.outputs.value | only(merged=true) | length
          merged_unknown: step.exact.outputs.value | only(merged=null) | length
      - name: classify-no-pr
        if: step.exact.outputs.value | length | eq(0)
        publish:
          classification: 'no_pr'
      - name: classify-one-open
        if: step.exact.outputs.value | only(state="open") | length | eq(1)
        publish:
          classification: 'exactly_one_open'
      - name: classify-ambiguous-open
        if:
          all:
            - step.exact.outputs.value | only(state="open") | length | ne(0)
            - step.exact.outputs.value | only(state="open") | length | ne(1)
        publish:
          classification: 'ambiguous_multiple_open'
      - name: classify-closed-history
        if:
          all:
            - step.exact.outputs.value | length | ne(0)
            - step.exact.outputs.value | only(state="open") | length | eq(0)
        publish:
          classification: 'only_closed_history'
'''


HELP_SNIPPET_REGISTRY["connector.gh.pr.list"] = {
    "snippet_coverage": "runner_verified",
    "canonical_examples": [{
        "name": f"gh_pr_list_{case}",
        "kind": "negative" if case == "unknown_metadata" else "positive",
        "form": "workflow_fragment",
        "summary": "List all matching candidates with head, head_owner, base, and state: all. Require complete results and known source identity before comparing the intended repository. The workflow publishes no pull request, exactly one open pull request, ambiguity, or closed history; it does not select a number or take an action automatically. A later workflow decision must require exactly one matching open pull request.",
        "yaml": _gh_pr_list_workflow(),
        "verification": {"kind": "runner_verified", "world": f"gh-pr-list-{case.replace('_', '-')}",
                         "insertion_mode": "workflow_fragment", "target": "connector.gh.pr.list",
                         "expected_status": "execution_error" if case == "unknown_metadata" else "ok"},
    } for case in ("no_pr", "exactly_one_open", "ambiguous_multiple_open", "only_closed_history", "unknown_metadata")],
}


def _gh_pr_create_workflow() -> str:
    """Exact create-only teaching policy; no implicit adoption of existing PRs."""
    return '''version: 0
workflow: create-new-branch-pull-request
# Explicit repository is an example choice; the action can also use the workflow GitHub repository context.
inputs:
  repository: {}
  head: {}
  head_owner: {}
  head_repository: {}
  head_repository_name:
    description: Source repository name without owner, used to check owner consistency.
  base: {}
  title: {}
  body: {}
  draft:
    default: true
  authorize_create:
    default: false
blocks:
  - steps:
      - name: require-authorization-and-source-identity
        gate:
          all:
            - inputs.authorize_create | eq(true)
            - inputs.draft | is_boolean
            - inputs.head_repository | lower | eq(format("{}/{}", inputs.head_owner, inputs.head_repository_name) | lower)
      - name: list-candidates
        uses: gh.pr.list
        with:
          repository: inputs.repository
          head: inputs.head
          head_owner: inputs.head_owner
          base: inputs.base
          state: 'all'
        register: candidates
      - name: require-complete-known-identity
        gate:
          all:
            - step.candidates.outputs.complete | eq(true)
            - step.candidates.outputs.items | length | eq(step.candidates.outputs.count)
            - step.candidates.outputs.items | only(head_repository!=null) | only(head_repository!="") | length | eq(step.candidates.outputs.count)
            - step.candidates.outputs.items | only(head_repository_key!=null) | only(head_repository_key!="") | length | eq(step.candidates.outputs.count)
            - step.candidates.outputs.items | only(head_owner!=null) | only(head_owner!="") | length | eq(step.candidates.outputs.count)
            - step.candidates.outputs.items | only(head_ref!=null) | only(head_ref!="") | length | eq(step.candidates.outputs.count)
            - step.candidates.outputs.items | only(base_repository!=null) | only(base_repository!="") | length | eq(step.candidates.outputs.count)
            - step.candidates.outputs.items | only(base_ref!=null) | only(base_ref!="") | length | eq(step.candidates.outputs.count)
      - name: select-exact-source-repository
        value: step.candidates.outputs.items | only(head_repository_key=inputs.head_repository | lower)
        register: exact
      # EXAMPLE workflow policy: refuse all existing PRs, including closed history.
      # The action independently rechecks open PRs; this list is not atomic authorization.
      - name: require-no-existing-pr
        gate: step.exact.outputs.value | length | eq(0)
      - name: create-pr
        uses: gh.pr.create
        with:
          repository: inputs.repository
          head: inputs.head
          head_owner: inputs.head_owner
          head_repository: inputs.head_repository
          base: inputs.base
          title: inputs.title
          body: inputs.body
          draft: inputs.draft
        register: creation
      - name: require-created-identity
        gate:
          all:
            - step.creation.outputs.created | eq(true)
            - step.creation.outputs.pull_number | is_integer
            - step.creation.outputs.pull_number | ne(0)
            - step.creation.outputs.repository | lower | eq(inputs.repository | lower)
      - name: observe-created-number
        uses: gh.pr
        with:
          repository: step.creation.outputs.repository
          pull_number: step.creation.outputs.pull_number
        register: final_pr
      - name: publish-created-pr
        publish:
          pull_number: step.creation.outputs.pull_number
          pull_ref: step.creation.outputs.pull_ref
          url: step.creation.outputs.url
          created: step.creation.outputs.created
          state: step.final_pr.outputs.state
'''


HELP_SNIPPET_REGISTRY["connector.gh.pr.create"] = {
    "snippet_coverage": "runner_verified",
    "canonical_examples": [{
        "name": "gh_pr_create_new_only", "kind": "positive", "form": "workflow_fragment",
        "summary": "Authorization defaults to false and draft defaults to true. Confirm the source repository, refuse existing matching history as this workflow's policy, create the pull request, then inspect the created pull request by its returned number. Action failures stop without retry or publication.",
        "yaml": _gh_pr_create_workflow(),
        "verification": {"kind": "runner_verified", "world": "gh-pr-create-new-only",
                         "insertion_mode": "workflow_fragment", "target": "connector.gh.pr.create",
                         "expected_status": "ok"},
    }],
}


def _gh_pr_merge_workflow(*, test_merge: bool, context_repository: bool = False) -> str:
    """The displayed document is also the fixture executor's complete input."""

    target = "test_merge" if test_merge else "head"
    context = "# Requires the GitHub repository context to be acme/mobile-app.\n# Supply that context through profile YAML: connectors: {gh: {repository: acme/mobile-app}}\n" if context_repository else ""
    repository_guard = """      - name: require-matching-repository
        gate: inputs.repository | eq("acme/mobile-app")
""" if context_repository else ""
    merge_repository = "" if context_repository else "          repository: inputs.repository\n"
    candidate_guards = """            - step.h.outputs.test_merge_state | eq("verified")
            - step.h.outputs.test_merge_head_sha | eq(step.h.outputs.head_sha)
            - step.h.outputs.test_merge_base_sha | eq(step.h.outputs.base_sha)
            - step.ci.outputs.test_merge_state | eq("verified")
            - step.ci.outputs.test_merge_sha | eq(step.h.outputs.test_merge_sha)
            - step.ci.outputs.test_merge_head_sha | eq(step.h.outputs.head_sha)
            - step.ci.outputs.test_merge_base_sha | eq(step.h.outputs.base_sha)
            - step.ci.outputs.base_sha | eq(step.h.outputs.base_sha)
            - step.ci.outputs.commit_sha | eq(step.h.outputs.test_merge_sha)
""" if test_merge else """            - step.ci.outputs.commit_sha | eq(step.h.outputs.head_sha)
"""
    return f"""version: 0
workflow: gh-pr-merge-{target.replace('_', '-')}{'-context' if context_repository else ''}
{context}inputs:
  repository:
    description: Explicit OWNER/REPO repository.
  pull_number:
    description: Pull request number.
  authorize_merge:
    default: false
    description: Explicit workflow authorization to submit a direct merge.
blocks:
  - steps:
      - name: require-merge-authorization
        gate: inputs.authorize_merge | eq(true)
{repository_guard}      - name: save-head
        uses: gh.pr
        with:
          repository: inputs.repository
          pull_number: inputs.pull_number
        register: h
      - name: require-standalone-head
        gate:
          all:
            - step.h.outputs.stack_state | eq("standalone")
            - step.h.outputs.head_sha | is_string
      - name: inspect-pinned-checks
        uses: gh.pr.checks
        with:
          repository: inputs.repository
          pull_number: inputs.pull_number
          target: '{target}'
          expected_head_sha: step.h.outputs.head_sha
        register: ci
      - name: require-pinned-trusted-ci
        gate:
          all:
            - step.ci.outputs.complete | eq(true)
            - step.ci.outputs.statuses_complete | eq(true)
            - step.ci.outputs.check_runs_complete | eq(true)
            - step.ci.outputs.head_sha | eq(step.h.outputs.head_sha)
            - step.ci.outputs.expected_head_sha | eq(step.h.outputs.head_sha)
            - step.ci.outputs.target | eq("{target}")
{candidate_guards}            - step.ci.outputs.overall_state | eq("success")
            - step.ci.outputs.checks | only(name="unit") | only(app_id=15368) | length | eq(1)
            - step.ci.outputs.checks | only(name="unit") | only(app_id=15368) | only(kind="check_run") | only(status="completed") | only(conclusion="success") | only(sha=step.ci.outputs.commit_sha) | length | eq(1)
      - name: submit-merge
        uses: gh.pr.merge
        with:
{merge_repository}          pull_number: inputs.pull_number
          merge_method: 'squash'
          expected_head_sha: step.h.outputs.head_sha
        register: submission
      - name: publish-submission
        publish:
          request_id: step.submission.outputs.request_id
          submission_state: step.submission.outputs.state
      - name: observe-saved-request-once
        if: step.submission.outputs.request_id | is_string
        uses: gh.pr.merge.request
        with:
{merge_repository}          pull_number: inputs.pull_number
          request_id: step.submission.outputs.request_id
        register: request
      - name: publish-request-observation
        if: step.submission.outputs.request_id | is_string
        publish:
          request_id: step.submission.outputs.request_id
          request_state: step.request.outputs.state
          request_message: step.request.outputs.message
      - name: confirm-pr
        uses: gh.pr
        with:
          repository: inputs.repository
          pull_number: inputs.pull_number
        register: final_pr
      - name: publish-confirmation
        publish:
          merged: step.final_pr.outputs.merged
          merge_commit_sha: step.final_pr.outputs.merge_commit_sha
"""


for _merge_handle in ("connector.gh.pr", "connector.gh.pr.checks", "connector.gh.pr.merge", "connector.gh.pr.merge.request"):
    _merge_entry = HELP_SNIPPET_REGISTRY.setdefault(_merge_handle, {"canonical_examples": []})
    _merge_entry["snippet_coverage"] = "runner_verified"
    for _test_merge, _context_repository in ((False, False), (True, False), (False, True)):
        _merge_world = "gh-pr-merge-test-merge" if _test_merge else "gh-pr-merge-head"
        if _context_repository:
            _merge_world += "-context"
        _merge_entry["canonical_examples"].append({
            "name": "gh_pr_async_merge_head_context" if _context_repository else "gh_pr_async_merge_test_merge" if _test_merge else "gh_pr_async_merge_head",
            "kind": "positive", "form": "workflow_fragment",
            "summary": "Authorize a merge explicitly, save the pull request source revision, and require the workflow's chosen checks for that saved revision before submitting a squash merge. Save the returned request ID, inspect it once when present, and then read the pull request again. Only the final pull request observation confirms whether it merged.",
            "yaml": _gh_pr_merge_workflow(test_merge=_test_merge, context_repository=_context_repository),
            "verification": {"kind": "runner_verified", "world": _merge_world,
                             "insertion_mode": "workflow_fragment", "target": _merge_handle,
                             "expected_status": "ok"},
        })
        if _context_repository:
            _merge_entry["canonical_examples"][-1]["summary"] += " With the workflow's GitHub repository context available, merge and request omit repository; explicit repository overrides remain supported. Pull-request reads and checks use an explicit input guarded to match that context."


def _git_remote_workflow() -> str:
    """Standalone local observer; destination policy belongs to its caller."""
    return """version: 0
workflow: inspect-configured-origin
inputs:
  remote:
    default: 'origin'
blocks:
  - steps:
      - name: observe-remote
        uses: git.remote
        with:
          remote: inputs.remote
        register: observed
      - name: require-existing-remote
        gate: step.observed.outputs.exists | eq(true)
      - name: publish-remote-facts
        publish:
          name: step.observed.outputs.name
          exists: step.observed.outputs.exists
          fetch_urls: step.observed.outputs.fetch_urls
          push_urls: step.observed.outputs.push_urls
          mirror: step.observed.outputs.mirror
      - name: count-fetch-urls
        value: step.observed.outputs.fetch_urls | length
        register: fetch_count
      - name: count-push-urls
        value: step.observed.outputs.push_urls | length
        register: push_count
      - name: publish-url-counts
        publish:
          fetch_count: step.fetch_count.outputs.value
          push_count: step.push_count.outputs.value
"""


HELP_SNIPPET_REGISTRY["connector.git.remote"] = {
    "snippet_coverage": "runner_verified",
    "canonical_examples": [{
        "name": "git_remote_" + case, "kind": "positive", "form": "workflow_fragment",
        "summary": (
            "Inspect a named remote and publish its name, existence, fetch destinations, push destinations, and mirror state. "
            "The workflow stops dependent work when the named remote is absent. Destination acceptance remains the "
            "author's decision; recorded destinations are observations, not proof that a later publication is appropriate."
        ),
        "yaml": _git_remote_workflow(),
        "verification": {"kind": "runner_verified", "world": "git-remote-" + case,
                         "insertion_mode": "workflow_fragment", "target": "connector.git.remote",
                         "expected_status": "ok" if case == "exists" else "execution_error"},
    } for case in ("exists", "missing")],
}


def _gh_actions_workflow(*, bridge: bool) -> str:
    """Exact public observer source shared across Actions bridge handles."""
    selection = """  pull_number: {}
  check_suite_id: {}
blocks:
  - steps:
      - name: inspect-checks
        uses: gh.pr.checks
        with:
          repository: inputs.repository
          pull_number: inputs.pull_number
          target: 'head'
        register: checks
      - name: require-complete-checks
        gate: step.checks.outputs.complete | eq(true)
      - name: require-suite-selector
        gate: inputs.check_suite_id | is_integer
      - name: select-suite-checks
        value: step.checks.outputs.checks | only(kind="check_run") | only(check_suite_id=inputs.check_suite_id)
        register: selected
      - name: require-selected-suite
        gate: step.selected.outputs.value | length | ne(0)
      - name: observe-run
        uses: gh.actions.run
        with:
          repository: inputs.repository
          check_suite_id: inputs.check_suite_id
        register: observed
""" if bridge else """  run_id: {}
blocks:
  - steps:
      - name: observe-run
        uses: gh.actions.run
        with:
          repository: inputs.repository
          run_id: inputs.run_id
        register: observed
"""
    return """version: 0
workflow: inspect-actions
inputs:
  repository: {}
""" + selection + """      - name: require-found-run
        gate: step.observed.outputs.found | eq(true)
      - name: observe-pinned-jobs
        uses: gh.actions.run.jobs
        with:
          repository: inputs.repository
          run_id: step.observed.outputs.run_id
          attempt: step.observed.outputs.run_attempt
        register: jobs
      - name: require-complete-jobs
        gate: step.jobs.outputs.complete | eq(true)
      - name: publish-observation
        publish:
          run_id: step.observed.outputs.run_id
          run_attempt: step.observed.outputs.run_attempt
          items: step.jobs.outputs.items
          count: step.jobs.outputs.count
          complete: step.jobs.outputs.complete
"""


GH_ACTIONS_TARGETS = ("connector.gh.actions.run", "connector.gh.actions.run.jobs",
                      "connector.gh.pr.checks", "connector.gh")
for _actions_handle in GH_ACTIONS_TARGETS:
    _entry = HELP_SNIPPET_REGISTRY.setdefault(_actions_handle, {"canonical_examples": []})
    _entry["snippet_coverage"] = "runner_verified"
    for _case in ("direct", "bridge", "null-suite", "no-run"):
        _entry["canonical_examples"].append({
            "name": "gh_actions_" + _case.replace("-", "_"),
            "kind": "positive", "form": "workflow_fragment",
            "summary": {
                "direct": "Observe a known run, then pass its registered run_id and latest observed run_attempt to pinned jobs. Require complete collection before publishing every job; count=0 is valid.",
                "bridge": "Read complete PR checks, select check runs by explicit check_suite_id (several checks may share a suite), resolve the suite through gh.actions.run, gate on found, and pass registered run_id/run_attempt to complete jobs. No run ID is guessed from a check ID or URL.",
                "null-suite": "The same bridge gates before run lookup when the suite selector is null. Nullable check_suite_id is normal; it cannot identify an Actions run.",
                "no-run": "The same bridge stops at the found gate when the suite has no associated Actions run (found=false). Jobs never receives a guessed run or null attempt.",
            }[_case] + " The workflow keeps run and attempt identities explicit, requires a complete job collection, and does not establish an atomic snapshot or merge policy.",
            "yaml": _gh_actions_workflow(bridge=_case != "direct"),
            "verification": {"kind": "runner_verified", "world": "gh-actions-" + _case,
                             "insertion_mode": "workflow_fragment", "target": _actions_handle,
                             "expected_status": "execution_error" if _case in {"null-suite", "no-run"} else "ok"},
        })


def _load_excerpt_text(
    *, path: str, start_line: int, end_line: int, source_lines: dict[str, list[str]] | None = None
) -> str:
    if source_lines is None:
        source_lines = {}
    if path not in source_lines:
        source_lines[path] = (_REPO_ROOT / path).read_text(encoding="utf-8").splitlines()
    lines = source_lines[path]
    excerpt = lines[start_line - 1 : end_line]
    return "\n".join(excerpt)


def describe_help_snippets() -> dict[str, JSONObject]:
    """Return published help-snippet metadata with rendered excerpt bodies."""

    payload: dict[str, JSONObject] = deepcopy(HELP_SNIPPET_REGISTRY)
    # Reuse each source's first read only for this catalog construction.
    source_lines: dict[str, list[str]] = {}
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
                    source_lines=source_lines,
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
