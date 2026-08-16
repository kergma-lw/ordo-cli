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
    "playbook.workflows": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "playbook_workflows_catalog_entry",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Publish one named workflow entry with launch metadata, operator guidance, and explicit state bindings in the playbook catalog.",
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
    "playbook.workflows.with": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "playbook_workflows_with_entry",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Provide entry-owned launch inputs for one published workflow, including values that feed the workflow and the entry working-directory expression.",
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
    "profile.overrides": {
        "snippet_coverage": "excerpt_verified",
        "canonical_examples": [
            {
                "name": "profile_overrides_block",
                "kind": "positive",
                "form": "field_fragment",
                "summary": "Publish one profile-scoped override record with a target, an opaque payload object, and a short reason note.",
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
                "summary": "Name the consumer-owned target key that this override record is for.",
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
                "summary": "Attach one opaque object payload that the named override target may interpret.",
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
                "summary": "Delete one stale local branch after the workflow has already made the intended cleanup decision.",
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
                "summary": "Create one ordinary Git commit from the current index after the workflow has already decided the staged changes are ready.",
                "source_example": "git-commit-management",
                "source_excerpt": {
                    "path": "examples/git-commit-management.yaml",
                    "start_line": 15,
                    "end_line": 18
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
                    "start_line": 19,
                    "end_line": 22
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
                    "start_line": 23,
                    "end_line": 26
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
                "summary": "Read a bounded Git commit-history slice when the workflow needs commit texts instead of diffs or arbitrary git log formatting.",
                "source_example": "git-commit-management",
                "source_excerpt": {
                    "path": "examples/git-commit-management.yaml",
                    "start_line": 9,
                    "end_line": 14
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
                "summary": "Inspect recent commit texts, then demonstrate ordinary commit creation, amend, and revert as distinct Git commit surfaces in one teaching workflow.",
                "source_example": "git-commit-management",
                "source_excerpt": {
                    "path": "examples/git-commit-management.yaml",
                    "start_line": 1,
                    "end_line": 31
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
                    "end_line": 20
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
                "summary": "Inspect the current branch's upstream-tracking configuration after confirming repository context.",
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
                "summary": "Inspect repository context and current-branch upstream tracking together so a workflow can separate repository facts from branch-tracking facts cleanly.",
                "source_example": "git-repo-upstream-inspection",
                "source_excerpt": {
                    "path": "examples/git-repo-upstream-inspection.yaml",
                    "start_line": 1,
                    "end_line": 17
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
                    "start_line": 18,
                    "end_line": 21
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
                    "end_line": 40
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
                    "start_line": 22,
                    "end_line": 25
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
                    "start_line": 26,
                    "end_line": 29
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
                    "start_line": 30,
                    "end_line": 35
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
                "summary": "Refresh one named remote before the workflow compares branch divergence or decides whether publishing is safe.",
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
                "summary": "Fetch from one remote, inspect divergence and upstream context, then push one local branch so inbound and outbound Git sync surfaces stay clearly separated.",
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
                "summary": "Publish one local branch to a remote after earlier workflow steps have already refreshed and checked the relevant synchronization context.",
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
                    "start_line": 6,
                    "end_line": 8
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
                    "end_line": 15
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
                    "start_line": 8,
                    "end_line": 11
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
