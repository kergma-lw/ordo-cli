# Authoring model

This page outlines the main authoring contracts used in workflows, playbooks, profiles, and runtime state.

Use this page when you need field-level contract details for authoring work.

## Full JSON reference

```json
{
  "connectors": [
    {
      "bootstrap": {
        "context_fields": [],
        "prerequisites": []
      },
      "namespace": "runtime",
      "operations": [
        {
          "deprecated": true,
          "effects": [
            "switch runtime profile for later execution in the current run"
          ],
          "examples": [
            {
              "inputs": {
                "profile": "string"
              },
              "reference": "runtime.profile.use"
            }
          ],
          "failure_modes": [
            "input_error",
            "execution_error"
          ],
          "inputs": {
            "profile": "string"
          },
          "invalidates_observations": [],
          "kind": "action",
          "maturity": "stable",
          "name": "profile.use",
          "outputs": {
            "profile": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [
            "workflow.step.profile_switch"
          ],
          "summary": "Legacy compatibility action for switching runtime execution to another declared profile",
          "tags": [
            "runtime",
            "action"
          ]
        }
      ]
    },
    {
      "bootstrap": {
        "context_fields": [
          "repository_root"
        ],
        "prerequisites": [
          "git binary available",
          "inside git repository"
        ]
      },
      "namespace": "git",
      "operations": [
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {},
              "reference": "git.branch"
            }
          ],
          "failure_modes": [
            "probe_failed"
          ],
          "inputs": {},
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "branch",
          "outputs": {
            "detached": "boolean",
            "ref": "string | null",
            "repository_root": "string",
            "value": "string | null"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Probe operation 'git.branch'",
          "tags": [
            "git",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [
            "create a new local branch"
          ],
          "examples": [
            {
              "inputs": {
                "branch": "string",
                "start_point": "string | null"
              },
              "reference": "git.branch.create"
            }
          ],
          "failure_modes": [
            "invalid_branch",
            "branch_exists",
            "start_point_not_found",
            "create_blocked"
          ],
          "inputs": {
            "branch": "string",
            "start_point": "string | null"
          },
          "invalidates_observations": [
            "git.branches",
            "git.ref.*"
          ],
          "kind": "action",
          "maturity": "stable",
          "name": "branch.create",
          "outputs": {
            "branch": "string",
            "start_point": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Action operation 'git.branch.create'",
          "tags": [
            "git",
            "action"
          ]
        },
        {
          "deprecated": false,
          "effects": [
            "delete a local non-default branch"
          ],
          "examples": [
            {
              "inputs": {
                "branch": "string"
              },
              "reference": "git.branch.delete"
            }
          ],
          "failure_modes": [
            "branch_not_found",
            "branch_checked_out",
            "default_branch_protected",
            "branch_not_merged",
            "delete_blocked"
          ],
          "inputs": {
            "branch": "string"
          },
          "invalidates_observations": [
            "git.branches",
            "git.ref.*"
          ],
          "kind": "action",
          "maturity": "stable",
          "name": "branch.delete",
          "outputs": {
            "branch": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Action operation 'git.branch.delete'",
          "tags": [
            "git",
            "action"
          ]
        },
        {
          "deprecated": false,
          "effects": [
            "switch current checkout to a local branch"
          ],
          "examples": [
            {
              "inputs": {
                "branch": "string"
              },
              "reference": "git.branch.switch"
            }
          ],
          "failure_modes": [
            "branch_not_found",
            "worktree_change_conflict",
            "unresolved_state",
            "switch_blocked"
          ],
          "inputs": {
            "branch": "string"
          },
          "invalidates_observations": [
            "git.branch",
            "git.branches",
            "git.upstream",
            "git.ref.*",
            "git.tag",
            "git.tags",
            "git.worktree",
            "git.worktrees",
            "git.state",
            "git.repo",
            "git.range",
            "git.commits"
          ],
          "kind": "action",
          "maturity": "stable",
          "name": "branch.switch",
          "outputs": {
            "branch": "string",
            "changed": "boolean"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Action operation 'git.branch.switch'",
          "tags": [
            "git",
            "action"
          ]
        },
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {},
              "reference": "git.branches"
            }
          ],
          "failure_modes": [
            "probe_failed"
          ],
          "inputs": {},
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "branches",
          "outputs": {
            "count": "integer",
            "current": "string | null",
            "items": [
              {
                "current": "boolean",
                "kind": "string",
                "name": "string",
                "ref": "string"
              }
            ],
            "repository_root": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Probe operation 'git.branches'",
          "tags": [
            "git",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [
            "rewrite the current HEAD commit"
          ],
          "examples": [
            {
              "inputs": {
                "message": "string | null"
              },
              "reference": "git.commit.amend"
            }
          ],
          "failure_modes": [
            "message_invalid",
            "nothing_to_amend",
            "amend_blocked"
          ],
          "inputs": {
            "message": "string | null"
          },
          "invalidates_observations": [
            "git.ref.*",
            "git.tag",
            "git.tags",
            "git.worktree",
            "git.worktrees",
            "git.state",
            "git.range",
            "git.commits"
          ],
          "kind": "action",
          "maturity": "stable",
          "name": "commit.amend",
          "outputs": {
            "branch": "string | null",
            "commit": "string",
            "previous_commit": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Action operation 'git.commit.amend'",
          "tags": [
            "git",
            "action"
          ]
        },
        {
          "deprecated": false,
          "effects": [
            "create a new commit from the current index"
          ],
          "examples": [
            {
              "inputs": {
                "message": "string"
              },
              "reference": "git.commit.create"
            }
          ],
          "failure_modes": [
            "message_invalid",
            "nothing_to_commit",
            "commit_blocked"
          ],
          "inputs": {
            "message": "string"
          },
          "invalidates_observations": [
            "git.ref.*",
            "git.tag",
            "git.tags",
            "git.worktree",
            "git.worktrees",
            "git.state",
            "git.range",
            "git.commits"
          ],
          "kind": "action",
          "maturity": "stable",
          "name": "commit.create",
          "outputs": {
            "branch": "string | null",
            "commit": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Action operation 'git.commit.create'",
          "tags": [
            "git",
            "action"
          ]
        },
        {
          "deprecated": false,
          "effects": [
            "create a new commit that reverts a target commit"
          ],
          "examples": [
            {
              "inputs": {
                "commit": "string"
              },
              "reference": "git.commit.revert"
            }
          ],
          "failure_modes": [
            "commit_not_found",
            "merge_commit_not_supported",
            "revert_conflict",
            "revert_blocked"
          ],
          "inputs": {
            "commit": "string"
          },
          "invalidates_observations": [
            "git.ref.*",
            "git.tag",
            "git.tags",
            "git.worktree",
            "git.worktrees",
            "git.state",
            "git.range",
            "git.commits"
          ],
          "kind": "action",
          "maturity": "stable",
          "name": "commit.revert",
          "outputs": {
            "branch": "string | null",
            "revert_commit": "string",
            "reverted_commit": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Action operation 'git.commit.revert'",
          "tags": [
            "git",
            "action"
          ]
        },
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {
                "limit": 5,
                "rev": "HEAD"
              },
              "reference": "git.commits"
            },
            {
              "inputs": {
                "limit": 3,
                "rev": "HEAD~10..HEAD"
              },
              "reference": "git.commits"
            }
          ],
          "failure_modes": [
            "probe_failed"
          ],
          "inputs": {
            "limit": "integer",
            "rev": "string"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "commits",
          "outputs": {
            "count": "integer",
            "items": [
              {
                "author_name": "string",
                "body": "string",
                "commit": "string",
                "committed_at": "string",
                "subject": "string",
                "text": "string"
              }
            ],
            "repository_root": "string",
            "rev": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Return a bounded readable list of commit texts from one revision scope with only minimal metadata. This probe is intentionally narrow: it does not expose patch text, changed files, diff stats, graph decoration, or arbitrary git log formatting.",
          "tags": [
            "git",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [
            "stage all current worktree changes into the index"
          ],
          "examples": [
            {
              "inputs": {},
              "reference": "git.index.add_all"
            }
          ],
          "failure_modes": [
            "stage_blocked"
          ],
          "inputs": {},
          "invalidates_observations": [
            "git.worktree",
            "git.state"
          ],
          "kind": "action",
          "maturity": "stable",
          "name": "index.add_all",
          "outputs": {
            "staged": "boolean"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Action operation 'git.index.add_all'",
          "tags": [
            "git",
            "action"
          ]
        },
        {
          "deprecated": false,
          "effects": [
            "apply a target commit onto the current checkout as a new commit"
          ],
          "examples": [
            {
              "inputs": {
                "commit": "string"
              },
              "reference": "git.integrate.cherry_pick"
            }
          ],
          "failure_modes": [
            "commit_not_found",
            "merge_commit_not_supported",
            "cherry_pick_conflict",
            "cherry_pick_blocked"
          ],
          "inputs": {
            "commit": "string"
          },
          "invalidates_observations": [
            "git.ref.*",
            "git.tag",
            "git.tags",
            "git.worktree",
            "git.worktrees",
            "git.state",
            "git.range",
            "git.commits"
          ],
          "kind": "action",
          "maturity": "stable",
          "name": "integrate.cherry_pick",
          "outputs": {
            "branch": "string | null",
            "head_commit": "string",
            "picked_commit": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Action operation 'git.integrate.cherry_pick'",
          "tags": [
            "git",
            "action"
          ]
        },
        {
          "deprecated": false,
          "effects": [
            "integrate a target ref into the current checkout using merge semantics"
          ],
          "examples": [
            {
              "inputs": {
                "ref": "string"
              },
              "reference": "git.integrate.merge"
            }
          ],
          "failure_modes": [
            "ref_not_found",
            "merge_conflict",
            "merge_blocked"
          ],
          "inputs": {
            "ref": "string"
          },
          "invalidates_observations": [
            "git.ref.*",
            "git.tag",
            "git.tags",
            "git.worktree",
            "git.worktrees",
            "git.state",
            "git.range",
            "git.commits"
          ],
          "kind": "action",
          "maturity": "stable",
          "name": "integrate.merge",
          "outputs": {
            "branch": "string | null",
            "head_commit": "string",
            "merged_ref": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Action operation 'git.integrate.merge'",
          "tags": [
            "git",
            "action"
          ]
        },
        {
          "deprecated": false,
          "effects": [
            "integrate a target ref into the current checkout using fast-forward-only semantics"
          ],
          "examples": [
            {
              "inputs": {
                "ref": "string"
              },
              "reference": "git.integrate.merge_ff_only"
            }
          ],
          "failure_modes": [
            "ref_not_found",
            "non_fast_forward",
            "merge_blocked"
          ],
          "inputs": {
            "ref": "string"
          },
          "invalidates_observations": [
            "git.ref.*",
            "git.tag",
            "git.tags",
            "git.worktree",
            "git.worktrees",
            "git.state",
            "git.range",
            "git.commits"
          ],
          "kind": "action",
          "maturity": "stable",
          "name": "integrate.merge_ff_only",
          "outputs": {
            "branch": "string | null",
            "head_commit": "string",
            "merged_ref": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Action operation 'git.integrate.merge_ff_only'",
          "tags": [
            "git",
            "action"
          ]
        },
        {
          "deprecated": false,
          "effects": [
            "rebase a non-default branch range onto a new base using rebase --onto semantics"
          ],
          "examples": [
            {
              "inputs": {
                "branch": "string",
                "onto": "string",
                "upstream": "string"
              },
              "reference": "git.integrate.rebase_onto"
            }
          ],
          "failure_modes": [
            "onto_not_found",
            "upstream_not_found",
            "branch_not_found",
            "default_branch_protected",
            "rebase_conflict",
            "rebase_blocked"
          ],
          "inputs": {
            "branch": "string",
            "onto": "string",
            "upstream": "string"
          },
          "invalidates_observations": [
            "git.ref.*",
            "git.tag",
            "git.tags",
            "git.worktree",
            "git.worktrees",
            "git.state",
            "git.range",
            "git.commits"
          ],
          "kind": "action",
          "maturity": "stable",
          "name": "integrate.rebase_onto",
          "outputs": {
            "branch": "string",
            "head_commit": "string",
            "onto": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Action operation 'git.integrate.rebase_onto'",
          "tags": [
            "git",
            "action"
          ]
        },
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {
                "base": "string",
                "head": "string"
              },
              "reference": "git.range"
            }
          ],
          "failure_modes": [
            "probe_failed"
          ],
          "inputs": {
            "base": "string",
            "head": "string"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "range",
          "outputs": {
            "ahead_count": "integer",
            "base": "string",
            "base_oid": "string",
            "behind_count": "integer",
            "head": "string",
            "head_oid": "string",
            "merge_base_oid": "string | null",
            "repository_root": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Probe operation 'git.range'",
          "tags": [
            "git",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {
                "ref": "string"
              },
              "reference": "git.ref"
            }
          ],
          "failure_modes": [
            "probe_failed"
          ],
          "inputs": {
            "ref": "string"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "ref",
          "outputs": {
            "exists": "boolean",
            "name": "string",
            "oid": "string | null",
            "repository_root": "string",
            "symbolic": "boolean",
            "symbolic_target": "string | null"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Probe operation 'git.ref'",
          "tags": [
            "git",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {},
              "reference": "git.repo"
            }
          ],
          "failure_modes": [
            "probe_failed"
          ],
          "inputs": {},
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "repo",
          "outputs": {
            "bare": "boolean",
            "common_dir": "string",
            "default_branch": "string | null",
            "exists": "boolean",
            "git_dir": "string",
            "head_ref": "string | null",
            "inside_work_tree": "boolean",
            "root": "string",
            "worktree_path": "string | null"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Probe operation 'git.repo'",
          "tags": [
            "git",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {},
              "reference": "git.stash"
            }
          ],
          "failure_modes": [
            "probe_failed"
          ],
          "inputs": {},
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "stash",
          "outputs": {
            "count": "integer",
            "items": [
              {
                "name": "string",
                "selector": "string",
                "summary": "string"
              }
            ],
            "repository_root": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Probe operation 'git.stash'",
          "tags": [
            "git",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {},
              "reference": "git.state"
            }
          ],
          "failure_modes": [
            "probe_failed"
          ],
          "inputs": {},
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "state",
          "outputs": {
            "branch": "string | null",
            "detached": "boolean",
            "has_staged_changes": "boolean",
            "has_unstaged_changes": "boolean",
            "has_untracked": "boolean",
            "repository_root": "string",
            "stash_count": "integer",
            "worktree_clean": "boolean"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Probe operation 'git.state'",
          "tags": [
            "git",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [
            "fetch refs from a remote into the local repository"
          ],
          "examples": [
            {
              "inputs": {
                "remote": "string"
              },
              "reference": "git.sync.fetch"
            }
          ],
          "failure_modes": [
            "remote_not_found",
            "fetch_blocked"
          ],
          "inputs": {
            "remote": "string"
          },
          "invalidates_observations": [
            "git.ref.*",
            "git.tag",
            "git.tags",
            "git.branches",
            "git.repo",
            "git.range",
            "git.commits"
          ],
          "kind": "action",
          "maturity": "stable",
          "name": "sync.fetch",
          "outputs": {
            "fetched": "boolean",
            "remote": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Action operation 'git.sync.fetch'",
          "tags": [
            "git",
            "action"
          ]
        },
        {
          "deprecated": false,
          "effects": [
            "push a local branch to a remote"
          ],
          "examples": [
            {
              "inputs": {
                "branch": "string",
                "remote": "string | null"
              },
              "reference": "git.sync.push"
            }
          ],
          "failure_modes": [
            "branch_not_found",
            "remote_not_found",
            "upstream_remote_missing",
            "non_fast_forward",
            "push_blocked"
          ],
          "inputs": {
            "branch": "string",
            "remote": "string | null"
          },
          "invalidates_observations": [],
          "kind": "action",
          "maturity": "stable",
          "name": "sync.push",
          "outputs": {
            "branch": "string",
            "remote": "string"
          },
          "preflight_observations": [
            {
              "probe": "git.branch",
              "with": {}
            },
            {
              "probe": "git.upstream",
              "with": {}
            },
            {
              "probe": "git.range",
              "with": {
                "base": "@{upstream}",
                "head": "{branch}"
              }
            }
          ],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Action operation 'git.sync.push'",
          "tags": [
            "git",
            "action"
          ]
        },
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {
                "name": "string"
              },
              "reference": "git.tag"
            }
          ],
          "failure_modes": [
            "probe_failed"
          ],
          "inputs": {
            "name": "string"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "tag",
          "outputs": {
            "annotated": "boolean | null",
            "exists": "boolean",
            "name": "string",
            "oid": "string | null",
            "ref": "string",
            "repository_root": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Probe operation 'git.tag'",
          "tags": [
            "git",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {
                "match": "string | null"
              },
              "reference": "git.tags"
            }
          ],
          "failure_modes": [
            "probe_failed"
          ],
          "inputs": {
            "match": "string | null"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "tags",
          "outputs": {
            "count": "integer",
            "items": [
              {
                "annotated": "boolean",
                "name": "string",
                "oid": "string",
                "ref": "string"
              }
            ],
            "latest": {
              "annotated": "boolean",
              "name": "string",
              "oid": "string",
              "ref": "string"
            },
            "repository_root": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Probe operation 'git.tags'",
          "tags": [
            "git",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {},
              "reference": "git.upstream"
            }
          ],
          "failure_modes": [
            "probe_failed"
          ],
          "inputs": {},
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "upstream",
          "outputs": {
            "branch": "string | null",
            "configured": "boolean",
            "remote": "string | null",
            "remote_branch": "string | null",
            "repository_root": "string",
            "upstream_ref": "string | null"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Probe operation 'git.upstream'",
          "tags": [
            "git",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {},
              "reference": "git.worktree"
            }
          ],
          "failure_modes": [
            "probe_failed"
          ],
          "inputs": {},
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "worktree",
          "outputs": {
            "clean": "boolean",
            "dirty_paths": [
              "string"
            ],
            "has_staged_changes": "boolean",
            "has_unstaged_changes": "boolean",
            "has_untracked": "boolean",
            "repository_root": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Probe operation 'git.worktree'",
          "tags": [
            "git",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {},
              "reference": "git.worktrees"
            }
          ],
          "failure_modes": [
            "probe_failed"
          ],
          "inputs": {},
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "worktrees",
          "outputs": {
            "count": "integer",
            "current_path": "string | null",
            "items": [
              {
                "bare": "boolean",
                "branch": "string | null",
                "current": "boolean",
                "detached": "boolean",
                "head": "string",
                "path": "string"
              }
            ],
            "repository_root": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Probe operation 'git.worktrees'",
          "tags": [
            "git",
            "probe"
          ]
        }
      ]
    },
    {
      "bootstrap": {
        "context_fields": [
          "host",
          "viewer",
          "scopes"
        ],
        "prerequisites": [
          "gh binary available",
          "GitHub auth available"
        ]
      },
      "namespace": "gh",
      "operations": [
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {
                "issue_number": "integer",
                "repository": "string"
              },
              "reference": "gh.issue"
            }
          ],
          "failure_modes": [
            "issue_not_found",
            "probe_failed"
          ],
          "inputs": {
            "issue_number": "integer",
            "repository": "string"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "issue",
          "outputs": {
            "assignees": [
              "object"
            ],
            "author": "object",
            "body": "string",
            "closed": "boolean",
            "closed_at": "string",
            "comments": "object",
            "created_at": "string",
            "id": "string",
            "labels": [
              "object"
            ],
            "milestone": "object",
            "number": "number",
            "project_items": [
              "object"
            ],
            "reaction_groups": [
              "object"
            ],
            "repository": "object",
            "state": "string",
            "state_reason": "string",
            "title": "string",
            "updated_at": "string",
            "url": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Probe operation 'gh.issue'",
          "tags": [
            "gh",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [
            "append text to GitHub issue body"
          ],
          "examples": [
            {
              "inputs": {
                "issue_number": "integer",
                "repository": "string",
                "separator": "string | null",
                "text": "string"
              },
              "reference": "gh.issue.body.append"
            }
          ],
          "failure_modes": [
            "issue_not_found",
            "text_invalid",
            "append_blocked"
          ],
          "inputs": {
            "issue_number": "integer",
            "repository": "string",
            "separator": "string | null",
            "text": "string"
          },
          "invalidates_observations": [],
          "kind": "action",
          "maturity": "stable",
          "name": "issue.body.append",
          "outputs": {
            "body": "string",
            "changed": "boolean",
            "issue_ref": "string",
            "url": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Action operation 'gh.issue.body.append'",
          "tags": [
            "gh",
            "action"
          ]
        },
        {
          "deprecated": false,
          "effects": [
            "replace GitHub issue body"
          ],
          "examples": [
            {
              "inputs": {
                "body": "string",
                "issue_number": "integer",
                "repository": "string"
              },
              "reference": "gh.issue.body.replace"
            }
          ],
          "failure_modes": [
            "issue_not_found",
            "body_invalid",
            "replace_blocked"
          ],
          "inputs": {
            "body": "string",
            "issue_number": "integer",
            "repository": "string"
          },
          "invalidates_observations": [],
          "kind": "action",
          "maturity": "stable",
          "name": "issue.body.replace",
          "outputs": {
            "body": "string",
            "changed": "boolean",
            "issue_ref": "string",
            "url": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Action operation 'gh.issue.body.replace'",
          "tags": [
            "gh",
            "action"
          ]
        },
        {
          "deprecated": false,
          "effects": [
            "close GitHub issue"
          ],
          "examples": [
            {
              "inputs": {
                "issue_number": "integer",
                "repository": "string"
              },
              "reference": "gh.issue.close"
            }
          ],
          "failure_modes": [
            "issue_not_found",
            "close_blocked"
          ],
          "inputs": {
            "issue_number": "integer",
            "repository": "string"
          },
          "invalidates_observations": [],
          "kind": "action",
          "maturity": "stable",
          "name": "issue.close",
          "outputs": {
            "closed": "boolean",
            "issue_ref": "string",
            "state": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Action operation 'gh.issue.close'",
          "tags": [
            "gh",
            "action"
          ]
        },
        {
          "deprecated": false,
          "effects": [
            "add GitHub issue comment"
          ],
          "examples": [
            {
              "inputs": {
                "body": "string",
                "issue_number": "integer",
                "repository": "string"
              },
              "reference": "gh.issue.comment.add"
            }
          ],
          "failure_modes": [
            "issue_not_found",
            "body_invalid",
            "comment_blocked"
          ],
          "inputs": {
            "body": "string",
            "issue_number": "integer",
            "repository": "string"
          },
          "invalidates_observations": [],
          "kind": "action",
          "maturity": "stable",
          "name": "issue.comment.add",
          "outputs": {
            "body": "string",
            "comment_id": "string",
            "issue_ref": "string",
            "url": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Action operation 'gh.issue.comment.add'",
          "tags": [
            "gh",
            "action"
          ]
        },
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {
                "issue_number": "integer",
                "limit": "integer",
                "repository": "string"
              },
              "reference": "gh.issue.comments"
            }
          ],
          "failure_modes": [
            "issue_not_found",
            "limit_invalid",
            "probe_failed"
          ],
          "inputs": {
            "issue_number": "integer",
            "limit": "integer",
            "repository": "string"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "issue.comments",
          "outputs": {
            "comments": [
              "object"
            ],
            "issue_ref": "string",
            "total_count": "number"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Probe operation 'gh.issue.comments'",
          "tags": [
            "gh",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [
            "create GitHub issue"
          ],
          "examples": [
            {
              "inputs": {
                "body": "string | null",
                "repository": "string",
                "title": "string"
              },
              "reference": "gh.issue.create"
            }
          ],
          "failure_modes": [
            "repository_not_found",
            "title_invalid",
            "create_blocked"
          ],
          "inputs": {
            "body": "string | null",
            "repository": "string",
            "title": "string"
          },
          "invalidates_observations": [
            "gh.issue"
          ],
          "kind": "action",
          "maturity": "stable",
          "name": "issue.create",
          "outputs": {
            "issue_ref": "string",
            "number": "integer",
            "repository": "string",
            "title": "string",
            "url": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Action operation 'gh.issue.create'",
          "tags": [
            "gh",
            "action"
          ]
        },
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {
                "pull_number": 42,
                "repository": "owner/repo"
              },
              "reference": "gh.pr"
            }
          ],
          "failure_modes": [
            "pull_not_found",
            "probe_failed"
          ],
          "inputs": {
            "pull_number": "integer",
            "repository": "string"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "pr",
          "outputs": {
            "additions": "integer",
            "author": "object",
            "base_ref": "string",
            "body": "string",
            "changed_files": "integer",
            "commits_count": "integer",
            "created_at": "string",
            "deletions": "integer",
            "draft": "boolean",
            "head_ref": "string",
            "head_sha": "string",
            "mergeable": "boolean",
            "mergeable_state": "string",
            "number": "integer",
            "repository": "string",
            "review_decision": "string",
            "state": "string",
            "title": "string",
            "updated_at": "string",
            "url": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Read normalized metadata from a GitHub pull request.",
          "tags": [
            "gh",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {
                "pull_number": "integer",
                "repository": "string"
              },
              "reference": "gh.pr.checks"
            }
          ],
          "failure_modes": [
            "pull_not_found",
            "checks_unavailable",
            "probe_failed"
          ],
          "inputs": {
            "pull_number": "integer",
            "repository": "string"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "pr.checks",
          "outputs": {
            "checks": [
              {
                "conclusion": "string",
                "context": "string",
                "kind": "string",
                "name": "string",
                "status": "string",
                "url": "string"
              }
            ],
            "failed_count": "integer",
            "head_sha": "string",
            "overall_state": "string",
            "pending_count": "integer",
            "pull_ref": "string",
            "skipped_count": "integer",
            "success_count": "integer",
            "total_count": "integer"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Read normalized status and check-run results from a GitHub pull request head.",
          "tags": [
            "gh",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {
                "limit": "integer",
                "pull_number": "integer",
                "repository": "string"
              },
              "reference": "gh.pr.comments"
            }
          ],
          "failure_modes": [
            "pull_not_found",
            "limit_invalid",
            "probe_failed"
          ],
          "inputs": {
            "limit": "integer",
            "pull_number": "integer",
            "repository": "string"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "pr.comments",
          "outputs": {
            "comments": [
              "object"
            ],
            "pull_ref": "string",
            "total_count": "integer"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Read regular conversation comments from a GitHub pull request.",
          "tags": [
            "gh",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {
                "limit": "integer",
                "pull_number": "integer",
                "repository": "string"
              },
              "reference": "gh.pr.review_comments"
            }
          ],
          "failure_modes": [
            "pull_not_found",
            "limit_invalid",
            "probe_failed"
          ],
          "inputs": {
            "limit": "integer",
            "pull_number": "integer",
            "repository": "string"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "pr.review_comments",
          "outputs": {
            "comments": [
              "object"
            ],
            "pull_ref": "string",
            "total_count": "integer"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Read line-level review comments from a GitHub pull request.",
          "tags": [
            "gh",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {
                "limit": "integer",
                "pull_number": "integer",
                "repository": "string"
              },
              "reference": "gh.pr.reviews"
            }
          ],
          "failure_modes": [
            "pull_not_found",
            "limit_invalid",
            "probe_failed"
          ],
          "inputs": {
            "limit": "integer",
            "pull_number": "integer",
            "repository": "string"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "pr.reviews",
          "outputs": {
            "pull_ref": "string",
            "reviews": [
              "object"
            ],
            "total_count": "integer"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Read submitted reviews from a GitHub pull request.",
          "tags": [
            "gh",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {
                "limit": "integer",
                "pull_number": "integer",
                "repository": "string"
              },
              "reference": "gh.pr.timeline"
            }
          ],
          "failure_modes": [
            "pull_not_found",
            "limit_invalid",
            "probe_failed"
          ],
          "inputs": {
            "limit": "integer",
            "pull_number": "integer",
            "repository": "string"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "pr.timeline",
          "outputs": {
            "events": [
              "object"
            ],
            "pull_ref": "string",
            "total_count": "integer"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Read normalized lifecycle events from a GitHub pull request timeline.",
          "tags": [
            "gh",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {
                "project_id": "string"
              },
              "reference": "gh.project"
            }
          ],
          "failure_modes": [
            "project_not_found",
            "probe_failed"
          ],
          "inputs": {
            "project_id": "string"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "project",
          "outputs": {
            "exists": "boolean",
            "id": "string",
            "title": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Probe operation 'gh.project'",
          "tags": [
            "gh",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {
                "field": "string",
                "project_id": "string"
              },
              "reference": "gh.project.field"
            }
          ],
          "failure_modes": [
            "project_not_found",
            "probe_failed"
          ],
          "inputs": {
            "field": "string",
            "project_id": "string"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "project.field",
          "outputs": {
            "exists": "boolean",
            "kind": "string",
            "name": "string",
            "options": [
              "string"
            ]
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Probe operation 'gh.project.field'",
          "tags": [
            "gh",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {
                "field": "string",
                "option": "string",
                "project_id": "string"
              },
              "reference": "gh.project.field.option"
            }
          ],
          "failure_modes": [
            "project_not_found",
            "probe_failed"
          ],
          "inputs": {
            "field": "string",
            "option": "string",
            "project_id": "string"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "project.field.option",
          "outputs": {
            "exists": "boolean"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Return whether one named allowed value exists in one GitHub Project field when that field exposes a selectable value set",
          "tags": [
            "gh",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {
                "issue_number": "integer",
                "project_id": "string",
                "repository": "string"
              },
              "reference": "gh.project.issue"
            }
          ],
          "failure_modes": [
            "issue_not_found",
            "project_not_found",
            "probe_failed"
          ],
          "inputs": {
            "issue_number": "integer",
            "project_id": "string",
            "repository": "string"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "project.issue",
          "outputs": {
            "estimate": "number",
            "exists": "boolean",
            "item_id": "string",
            "iteration": "string",
            "priority": "string",
            "size": "string",
            "status": "string",
            "type": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Probe operation 'gh.project.issue'",
          "tags": [
            "gh",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [
            "add GitHub issue to project"
          ],
          "examples": [
            {
              "inputs": {
                "issue_number": "integer",
                "project_id": "string",
                "repository": "string"
              },
              "reference": "gh.project.issue.add"
            }
          ],
          "failure_modes": [
            "issue_not_found",
            "project_not_found",
            "add_blocked"
          ],
          "inputs": {
            "issue_number": "integer",
            "project_id": "string",
            "repository": "string"
          },
          "invalidates_observations": [
            "gh.project.issue"
          ],
          "kind": "action",
          "maturity": "stable",
          "name": "project.issue.add",
          "outputs": {
            "added": "boolean",
            "issue_ref": "string",
            "item_id": "string",
            "project_id": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Action operation 'gh.project.issue.add'",
          "tags": [
            "gh",
            "action"
          ]
        },
        {
          "deprecated": false,
          "effects": [
            "set one GitHub project issue iteration field by field name"
          ],
          "examples": [
            {
              "inputs": {
                "field": "string",
                "issue_number": "integer",
                "iteration": "string",
                "project_id": "string",
                "repository": "string"
              },
              "reference": "gh.project.issue.field_iteration.set"
            }
          ],
          "failure_modes": [
            "issue_not_found",
            "project_not_found",
            "field_not_found",
            "field_kind_unsupported",
            "iteration_not_found",
            "field_update_blocked"
          ],
          "inputs": {
            "field": "string",
            "issue_number": "integer",
            "iteration": "string",
            "project_id": "string",
            "repository": "string"
          },
          "invalidates_observations": [
            "gh.project.issue"
          ],
          "kind": "action",
          "maturity": "stable",
          "name": "project.issue.field_iteration.set",
          "outputs": {
            "changed": "boolean",
            "field": "string",
            "issue_ref": "string",
            "item_id": "string",
            "iteration": "string",
            "project_id": "string"
          },
          "preflight_observations": [
            {
              "fields": [
                "exists"
              ],
              "probe": "gh.project.issue",
              "with": {
                "issue_number": "{issue_number}",
                "project_id": "{project_id}",
                "repository": "{repository}"
              }
            },
            {
              "fields": [
                "exists"
              ],
              "probe": "gh.project.field",
              "with": {
                "field": "{field}",
                "project_id": "{project_id}"
              }
            }
          ],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Action operation 'gh.project.issue.field_iteration.set'",
          "tags": [
            "gh",
            "action"
          ]
        },
        {
          "deprecated": false,
          "effects": [
            "set one GitHub project issue number field by field name"
          ],
          "examples": [
            {
              "inputs": {
                "field": "string",
                "issue_number": "integer",
                "project_id": "string",
                "repository": "string",
                "value": "number"
              },
              "reference": "gh.project.issue.field_number.set"
            }
          ],
          "failure_modes": [
            "issue_not_found",
            "project_not_found",
            "field_not_found",
            "field_kind_unsupported",
            "field_value_invalid",
            "field_update_blocked"
          ],
          "inputs": {
            "field": "string",
            "issue_number": "integer",
            "project_id": "string",
            "repository": "string",
            "value": "number"
          },
          "invalidates_observations": [
            "gh.project.issue"
          ],
          "kind": "action",
          "maturity": "stable",
          "name": "project.issue.field_number.set",
          "outputs": {
            "changed": "boolean",
            "field": "string",
            "issue_ref": "string",
            "item_id": "string",
            "project_id": "string",
            "value": "number"
          },
          "preflight_observations": [
            {
              "fields": [
                "exists"
              ],
              "probe": "gh.project.issue",
              "with": {
                "issue_number": "{issue_number}",
                "project_id": "{project_id}",
                "repository": "{repository}"
              }
            },
            {
              "fields": [
                "exists"
              ],
              "probe": "gh.project.field",
              "with": {
                "field": "{field}",
                "project_id": "{project_id}"
              }
            }
          ],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Action operation 'gh.project.issue.field_number.set'",
          "tags": [
            "gh",
            "action"
          ]
        },
        {
          "deprecated": false,
          "effects": [
            "set one GitHub project issue single-select field by field name"
          ],
          "examples": [
            {
              "inputs": {
                "field": "string",
                "issue_number": "integer",
                "option": "string",
                "project_id": "string",
                "repository": "string"
              },
              "reference": "gh.project.issue.field_single_select.set"
            }
          ],
          "failure_modes": [
            "issue_not_found",
            "project_not_found",
            "field_not_found",
            "field_kind_unsupported",
            "option_not_found",
            "field_update_blocked"
          ],
          "inputs": {
            "field": "string",
            "issue_number": "integer",
            "option": "string",
            "project_id": "string",
            "repository": "string"
          },
          "invalidates_observations": [
            "gh.project.issue"
          ],
          "kind": "action",
          "maturity": "stable",
          "name": "project.issue.field_single_select.set",
          "outputs": {
            "changed": "boolean",
            "field": "string",
            "issue_ref": "string",
            "item_id": "string",
            "option": "string",
            "project_id": "string"
          },
          "preflight_observations": [
            {
              "fields": [
                "exists"
              ],
              "probe": "gh.project.issue",
              "with": {
                "issue_number": "{issue_number}",
                "project_id": "{project_id}",
                "repository": "{repository}"
              }
            },
            {
              "fields": [
                "exists"
              ],
              "probe": "gh.project.field",
              "with": {
                "field": "{field}",
                "project_id": "{project_id}"
              }
            },
            {
              "fields": [
                "exists"
              ],
              "probe": "gh.project.field.option",
              "with": {
                "field": "{field}",
                "option": "{option}",
                "project_id": "{project_id}"
              }
            }
          ],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Action operation 'gh.project.issue.field_single_select.set'",
          "tags": [
            "gh",
            "action"
          ]
        },
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {
                "project_id": "PVT_demo"
              },
              "reference": "gh.project.items",
              "why": "Load normalized project membership facts without mutating project state."
            },
            {
              "inputs": {
                "content_kind": "Issue",
                "filters": [
                  {
                    "field": "Status",
                    "value": "Ready"
                  }
                ],
                "project_id": "PVT_demo"
              },
              "reference": "gh.project.items",
              "why": "Narrow one project scan to issue-like items whose Status field equals Ready."
            },
            {
              "inputs": {
                "content_kind": "Issue",
                "content_refs": [
                  "owner/repo#7",
                  "owner/repo#8"
                ],
                "filters": [
                  {
                    "field": "Type",
                    "value": "Task"
                  }
                ],
                "project_id": "PVT_demo"
              },
              "reference": "gh.project.items",
              "why": "Intersect one project item query with one explicit set of GitHub content references."
            }
          ],
          "failure_modes": [
            "project_not_found",
            "unknown_field",
            "ambiguous_field",
            "unsupported_field_type",
            "invalid_filter_value",
            "invalid_content_ref",
            "probe_failed"
          ],
          "inputs": {
            "content_kind": "string",
            "content_refs": [
              "string"
            ],
            "filters": [
              {
                "field": "string",
                "value": "scalar"
              }
            ],
            "project_id": "string"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "project.items",
          "outputs": {
            "count": "integer",
            "items": [
              {
                "content_kind": "string",
                "item_id": "string",
                "number": "integer",
                "repository": "string",
                "title": "string",
                "url": "string"
              }
            ]
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Return normalized GitHub Project items for one project membership scan",
          "tags": [
            "gh",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {
                "content_kind": "Issue",
                "project_id": "PVT_demo"
              },
              "reference": "gh.project.items.details",
              "why": "Load project-scoped issue details including state and labels."
            },
            {
              "inputs": {
                "content_kind": "Issue",
                "content_refs": [
                  "owner/repo#7",
                  "owner/repo#8"
                ],
                "filters": [
                  {
                    "field": "Type",
                    "value": "Task"
                  }
                ],
                "project_id": "PVT_demo"
              },
              "reference": "gh.project.items.details",
              "why": "Load detailed facts for one explicit subset of project-backed GitHub content."
            }
          ],
          "failure_modes": [
            "project_not_found",
            "unknown_field",
            "ambiguous_field",
            "unsupported_field_type",
            "invalid_filter_value",
            "invalid_content_ref",
            "probe_failed"
          ],
          "inputs": {
            "content_kind": "string",
            "content_refs": [
              "string"
            ],
            "filters": [
              {
                "field": "string",
                "value": "scalar"
              }
            ],
            "project_id": "string"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "project.items.details",
          "outputs": {
            "count": "integer",
            "items": [
              {
                "content_kind": "string",
                "item_id": "string",
                "label_names": [
                  "string"
                ],
                "number": "integer",
                "repository": "string",
                "state": "string",
                "title": "string",
                "url": "string"
              }
            ]
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Return normalized GitHub Project items with stable content details",
          "tags": [
            "gh",
            "probe"
          ]
        }
      ]
    },
    {
      "bootstrap": {
        "context_fields": [
          "shell",
          "working_directory"
        ],
        "prerequisites": [
          "supported shell available"
        ]
      },
      "namespace": "shell",
      "operations": [
        {
          "deprecated": false,
          "effects": [
            "execute shell command"
          ],
          "examples": [
            {
              "inputs": {
                "command": "string"
              },
              "reference": "shell.command"
            }
          ],
          "failure_modes": [
            "command_failed",
            "action_failed"
          ],
          "inputs": {
            "command": "string"
          },
          "invalidates_observations": [],
          "kind": "action",
          "maturity": "stable",
          "name": "command",
          "outputs": {
            "exit_code": "integer",
            "stderr": "string",
            "stdout": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Action operation 'shell.command'",
          "tags": [
            "shell",
            "action"
          ]
        }
      ]
    },
    {
      "bootstrap": {
        "context_fields": [],
        "prerequisites": []
      },
      "namespace": "fs",
      "operations": [
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {
                "path": "/workspace/app.env"
              },
              "reference": "fs.file"
            }
          ],
          "failure_modes": [
            "path_not_found",
            "not_a_file",
            "content_unavailable",
            "probe_failed"
          ],
          "inputs": {
            "path": "string"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "file",
          "outputs": {
            "content": "string",
            "exists": "boolean",
            "group": "string",
            "kind": "string",
            "line_count": "integer",
            "modified_at": "string",
            "owner": "string",
            "path": "string",
            "permissions": "string",
            "size": "integer"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Observe one filesystem path as one file snapshot with canonical content and file metadata.",
          "tags": [
            "fs",
            "probe"
          ]
        }
      ]
    }
  ],
  "document_kind": "model",
  "local_expressions": {
    "pipeline_filters": [
      {
        "argument_count": 0,
        "input_type": "string",
        "name": "lower",
        "output_type": "string"
      },
      {
        "argument_count": 0,
        "input_type": "string",
        "name": "trim",
        "output_type": "string"
      },
      {
        "argument_count": 0,
        "input_type": "string",
        "name": "slug",
        "output_type": "string"
      },
      {
        "argument_count": 1,
        "input_type": "json",
        "name": "eq",
        "output_type": "boolean"
      },
      {
        "argument_count": 1,
        "input_type": "json",
        "name": "ne",
        "output_type": "boolean"
      },
      {
        "argument_count": 0,
        "input_type": "boolean",
        "name": "not",
        "output_type": "boolean"
      },
      {
        "argument_count": 0,
        "input_type": "json",
        "name": "is_string",
        "output_type": "boolean"
      },
      {
        "argument_count": 0,
        "input_type": "json",
        "name": "is_number",
        "output_type": "boolean"
      },
      {
        "argument_count": 0,
        "input_type": "json",
        "name": "is_integer",
        "output_type": "boolean"
      },
      {
        "argument_count": 0,
        "input_type": "json",
        "name": "is_boolean",
        "output_type": "boolean"
      },
      {
        "argument_count": 1,
        "input_type": "json",
        "name": "in",
        "output_type": "boolean"
      },
      {
        "argument_count": 1,
        "input_type": "json",
        "name": "field",
        "output_type": "json"
      },
      {
        "argument_count": 0,
        "input_type": "json",
        "name": "flatten",
        "output_type": "json"
      },
      {
        "argument_count": 0,
        "input_type": "json",
        "name": "first",
        "output_type": "json"
      },
      {
        "argument_count": 0,
        "input_type": "json",
        "name": "last",
        "output_type": "json"
      },
      {
        "argument_count": 0,
        "input_type": "json",
        "name": "length",
        "output_type": "number"
      },
      {
        "argument_count": 0,
        "input_type": "json",
        "name": "unique",
        "output_type": "json"
      }
    ]
  },
  "playbook": {
    "activation_semantics": {
      "discovery": {
        "missing": "playbook.discovery.missing",
        "path": ".ordo/ordo.yaml",
        "strategy": "cwd_relative_single_path"
      },
      "pre_run": {
        "effect": "executes_before_requested_workflow_in_same_runtime_session",
        "item_type": "pre_run_entry",
        "launch_context_boundary": "playbook_owned",
        "optional": [
          "state_bindings"
        ],
        "requires": [
          "file"
        ],
        "state_dependency_boundary": "must_not_widen_main_workflow_state_contract"
      },
      "profile_entries": {
        "requires": [
          "file"
        ]
      },
      "state_entries": {
        "requires": [
          "path"
        ]
      },
      "workflow_entries": {
        "optional": [
          "description",
          "category",
          "when",
          "working_directory",
          "state_bindings"
        ],
        "requires": [
          "file"
        ]
      }
    },
    "defaults_fields": [
      {
        "name": "profile",
        "required": false,
        "runtime_effect": "selects_active_profile",
        "type": "string"
      },
      {
        "expression_allowed_roots": [
          "inputs"
        ],
        "expression_forbidden_roots": [
          "state",
          "step"
        ],
        "expression_surface": "activation_input_value_expression",
        "expression_syntax": "${...}",
        "name": "working_directory",
        "required": false,
        "resolution_base": "playbook_dir",
        "runtime_effect": "sets_default_execution_working_directory",
        "type": "string"
      }
    ],
    "discovery": {
      "path": ".ordo/ordo.yaml"
    },
    "document_kind": "playbook",
    "pre_run_entry_fields": [
      {
        "name": "file",
        "required": true,
        "type": "string"
      },
      {
        "documentation_role": "playbook_owned_pre_run_state_bindings",
        "name": "state_bindings",
        "required": false,
        "type": "object"
      }
    ],
    "profile_entry_fields": [
      {
        "name": "file",
        "required": true,
        "type": "string"
      }
    ],
    "state_entry_fields": [
      {
        "name": "path",
        "required": true,
        "type": "string"
      }
    ],
    "top_level_fields": [
      {
        "name": "version",
        "required": true,
        "type": "integer"
      },
      {
        "name": "pre_run",
        "required": false,
        "type": "array"
      },
      {
        "name": "states",
        "required": true,
        "type": "object"
      },
      {
        "name": "defaults",
        "required": false,
        "type": "object"
      },
      {
        "name": "workflows",
        "required": true,
        "type": "object"
      },
      {
        "name": "profiles",
        "required": false,
        "type": "object"
      }
    ],
    "version": 1,
    "workflow_entry_fields": [
      {
        "name": "file",
        "required": true,
        "type": "string"
      },
      {
        "documentation_role": "project_local_workflow_summary",
        "name": "description",
        "required": false,
        "type": "string"
      },
      {
        "documentation_role": "project_local_workflow_catalog_group",
        "name": "category",
        "required": false,
        "runtime_effect": "published_metadata_only",
        "type": "string"
      },
      {
        "documentation_role": "operator_workflow_selection_guidance",
        "name": "when",
        "required": false,
        "runtime_effect": "published_metadata_only",
        "type": "string"
      },
      {
        "expression_allowed_roots": [
          "inputs"
        ],
        "expression_forbidden_roots": [
          "state",
          "step"
        ],
        "expression_surface": "activation_input_value_expression",
        "expression_syntax": "${...}",
        "name": "working_directory",
        "required": false,
        "resolution_base": "playbook_dir",
        "runtime_effect": "sets_execution_working_directory",
        "type": "string"
      },
      {
        "name": "state_bindings",
        "required": false,
        "type": "object"
      }
    ]
  },
  "profile": {
    "compose_semantics": {
      "checks": {
        "order": "left_to_right",
        "strategy": "deduplicated_union"
      },
      "inputs": {
        "conflict": "validation_error",
        "strategy": "first_writer_wins"
      },
      "launchers": {
        "conflict": "validation_error",
        "conflict_key": "launcher_name",
        "status": "deprecated",
        "strategy": "first_writer_wins"
      },
      "overrides": {
        "conflict": "validation_error",
        "conflict_key": "target"
      },
      "working_directory": {
        "conflict": "validation_error",
        "strategy": "first_writer_wins"
      }
    },
    "document_kind": "profile",
    "launcher_fields": [
      {
        "name": "file",
        "required": false,
        "type": "string"
      },
      {
        "name": "connector",
        "required": false,
        "type": "string"
      },
      {
        "name": "before",
        "required": false,
        "type": "string"
      },
      {
        "name": "after",
        "required": false,
        "type": "string"
      }
    ],
    "override_fields": [
      {
        "name": "target",
        "required": true,
        "type": "string"
      },
      {
        "name": "with",
        "required": false,
        "type": "object"
      },
      {
        "name": "reason",
        "required": false,
        "type": "string"
      }
    ],
    "top_level_fields": [
      {
        "name": "name",
        "required": true,
        "type": "string"
      },
      {
        "name": "inputs",
        "required": false,
        "runtime_effect": "applies_missing_workflow_inputs",
        "type": "object"
      },
      {
        "expression_allowed_roots": [
          "inputs"
        ],
        "expression_forbidden_roots": [
          "state",
          "step"
        ],
        "expression_surface": "activation_input_value_expression",
        "expression_syntax": "${...}",
        "name": "working_directory",
        "required": false,
        "resolution_base": "playbook_dir",
        "runtime_effect": "sets_profile_execution_working_directory",
        "type": "string"
      },
      {
        "name": "checks",
        "required": false,
        "runtime_effect": "published_metadata_only",
        "type": "array"
      },
      {
        "name": "overrides",
        "required": false,
        "runtime_effect": "published_metadata_only",
        "type": "array"
      },
      {
        "name": "launchers",
        "preferred_alternative": "published_routines",
        "required": false,
        "runtime_effect": "publishes_profile_scoped_launchers",
        "status": "deprecated",
        "type": "object"
      }
    ],
    "workflow_apply_semantics": {
      "checks": {
        "mutates_workflow_contract": false
      },
      "inputs": {
        "conflict": "validation_error",
        "may_add_missing": true,
        "may_override_explicit_workflow_values": false
      },
      "launchers": {
        "mutates_workflow_steps": false,
        "published_as_explicit_metadata": true,
        "status": "deprecated"
      },
      "overrides": {
        "mutates_workflow_steps": false,
        "published_as_explicit_metadata": true
      },
      "working_directory": {
        "mutates_workflow_steps": false,
        "published_as_explicit_metadata": true
      }
    }
  },
  "representation_adapters": {
    "families": [
      {
        "actions": [],
        "name": "key_value",
        "selectors": [],
        "shortcuts": [],
        "summary": "Interpret a plain-text root as a flat key/value object using a required literal separator parameter."
      },
      {
        "actions": [
          "add",
          "append",
          "replace",
          "remove"
        ],
        "name": "markdown",
        "selectors": [
          "prelude",
          "[\"title\"]",
          "[n]",
          ".blocks(\"kind\")"
        ],
        "shortcuts": [
          "list",
          "lists",
          "list_items",
          "task_list",
          "task_lists",
          "task_list_items",
          "paragraph",
          "paragraphs",
          "prelude"
        ],
        "summary": "Select and transform markdown sections, blocks, and lists through a family-owned path surface."
      },
      {
        "actions": [
          "append",
          "replace",
          "remove"
        ],
        "name": "text",
        "selectors": [
          "lines",
          "find(\"literal\")",
          "finds(\"literal\")",
          "before(\"literal\")",
          "after(\"literal\")",
          "[n]"
        ],
        "shortcuts": [],
        "summary": "Select and transform plain-text roots through literal narrowing, line projection, and terminal text mutation."
      }
    ],
    "shared_seam": {
      "family_owned_body": true,
      "host_binding_rules": [
        "host references do not appear bare inside adapter-owned body syntax",
        "outer bindings are resolved before adapter-family evaluation"
      ],
      "outer_binding_form": " with{...}",
      "read_write_boundary": {
        "read": "returns selected_or_derived_value",
        "write": "returns updated_root_value"
      }
    }
  },
  "state": {
    "document_kind": "state_contract",
    "invalid_path_rules": [
      {
        "message": "state path must start with 'state'",
        "name": "root_must_be_state"
      },
      {
        "message": "state path key reference must use dotted inputs form such as 'inputs.task_key'",
        "name": "key_reference_must_use_dotted_inputs"
      },
      {
        "message": "state path must not contain trailing content",
        "name": "no_trailing_content"
      }
    ],
    "path_forms": {
      "root": "state",
      "root_reference": "inputs",
      "shape": "state.<role>[inputs.<key>][.<field>...]",
      "supports_hyphenated_roles": true,
      "supports_nested_fields": true
    },
    "runtime_rules": [
      {
        "error_code": "runtime.state.binding_missing",
        "message": "state role must be bound before runtime access",
        "name": "bound_role_required"
      },
      {
        "error_code": "runtime.state.key_invalid",
        "message": "state key reference must resolve to a scalar value",
        "name": "scalar_key_required"
      },
      {
        "error_code": "runtime.state.declaration_missing",
        "message": "undeclared state locations are runtime errors",
        "name": "declared_location_required"
      }
    ],
    "storage_document": {
      "root_type": "object",
      "top_level_keys": "user-defined"
    },
    "workflow_surface": {
      "state_binding_field": "state_bindings",
      "state_needs_field": "state_needs",
      "step_state_delete_field": "state_delete",
      "step_state_set_field": "state_set",
      "storage_targets_field": "states"
    }
  },
  "workflow": {
    "block_forms": [
      {
        "name": "guard_block",
        "optional_fields": [],
        "required_fields": [
          "guards"
        ]
      },
      {
        "name": "step_block",
        "optional_fields": [],
        "required_fields": [
          "steps"
        ]
      },
      {
        "name": "include_block",
        "optional_fields": [
          "with"
        ],
        "required_fields": [
          "include"
        ]
      }
    ],
    "document_kind": "workflow",
    "guard_forms": [
      {
        "name": "operation_call",
        "shape": {
          "uses": "string",
          "with": "object"
        },
        "status": "compatibility_only"
      },
      {
        "name": "expression",
        "shape": "string",
        "status": "stable_preferred"
      }
    ],
    "include_contract": {
      "authoring_role": "workflow_fragment_reuse",
      "call_fields": [
        {
          "name": "include",
          "required": true,
          "type": "string"
        },
        {
          "authoring_role": "fragment_argument_bindings",
          "name": "with",
          "required": false,
          "type": "object"
        }
      ],
      "cycle_detection": "current_expansion_stack",
      "directive_field": "include",
      "error_codes": [
        "load.workflow.include.not_found",
        "load.workflow.include.cycle",
        "load.workflow.include.depth",
        "load.workflow.include.forbidden_path",
        "load.workflow.include.not_file",
        "load.workflow.include.with.type",
        "load.workflow.include.args.invalid_declaration",
        "load.workflow.include.args.missing",
        "load.workflow.include.args.unknown",
        "load.workflow.include.args.type"
      ],
      "expansion_semantics": "resolve_bind_expand_whole_node_replacement",
      "extension_probe_order": [
        ".yaml",
        ".yml"
      ],
      "fragment_argument_access_surface": "args.name",
      "fragment_argument_declaration_forms": [
        {
          "name": "required_short_form",
          "shape": "arg_name: string_type_name"
        },
        {
          "name": "object_form",
          "shape": {
            "default": "json_value_optional",
            "required": "boolean_optional",
            "type": "string"
          }
        }
      ],
      "fragment_argument_default_semantics": {
        "default_makes_argument_optional": true,
        "default_null_is_valid": true,
        "omitted_argument_is_distinct_from_explicit_null_binding": true
      },
      "fragment_metadata_fields": [
        {
          "name": "description",
          "required": false,
          "type": "string"
        },
        {
          "authoring_role": "declares_fragment_local_inputs",
          "name": "args",
          "required": false,
          "type": "object"
        }
      ],
      "max_depth": 32,
      "search_order": [
        "including_file_dir",
        "launch_dir",
        "launch_dir_dot_ordo",
        "home_dot_ordo",
        "built_in_includes_dir"
      ],
      "state_scope": "global_across_assembled_workflow",
      "step_scope": "local_to_workflow_or_fragment_expansion_scope",
      "stops_on_first_match": true,
      "targets": "files_only",
      "validation_boundary": "assembled_workflow_after_include_expansion_and_argument_binding"
    },
    "inputs_contract": {
      "access_surface": "inputs.name",
      "declaration_fields": [
        {
          "authoring_role": "input_meaning",
          "name": "description",
          "required": false,
          "type": "string"
        },
        {
          "authoring_role": "input_guidance",
          "name": "hint",
          "required": false,
          "type": "string",
          "validation_effect": "none"
        }
      ],
      "declaration_shape": "mapping",
      "declared_keys_required_at_activation": true,
      "empty_string_is_distinct_value": true,
      "null_is_distinct_from_missing": true,
      "rejects_unknown_activation_inputs": true,
      "scope": "global",
      "validated_by": "runtime"
    },
    "run_contract": {
      "authoring_role": "workflow_fragment_invocation",
      "body_forms": [
        "named_run_target",
        "inline_repeated_steps"
      ],
      "call_fields": [
        {
          "name": "run",
          "required": true,
          "type": "string"
        },
        {
          "authoring_role": "inline_repeated_body",
          "name": "steps",
          "required": false,
          "type": "array"
        },
        {
          "authoring_role": "caller_scoped_invocation_condition",
          "name": "if",
          "required": false,
          "type": "string"
        },
        {
          "authoring_role": "fragment_argument_bindings",
          "name": "with",
          "required": false,
          "type": "object"
        },
        {
          "authoring_role": "bounded_fan_out_source",
          "name": "for_each",
          "required": false,
          "type": "runtime_value"
        },
        {
          "authoring_role": "aggregate_invocation_result",
          "name": "register",
          "required": false,
          "type": "string"
        }
      ],
      "caller_scoped_binding_surface": [
        "inputs",
        "state",
        "step"
      ],
      "caller_scoped_condition_surface": [
        "inputs",
        "state",
        "step"
      ],
      "directive_field": "run",
      "execution_semantics": "runtime_scoped_fragment_invocation",
      "fan_out_surface": {
        "forbidden_nested_surfaces": [
          "for_each",
          "guards"
        ],
        "inner_if_scope": "per_iteration_inner_step",
        "inner_register_scope": "iteration_local",
        "inner_step_scope": [
          "inputs",
          "state",
          "step",
          "item"
        ],
        "item_binding": "item",
        "outer_if_scope": "whole_invocation_step",
        "outer_register_scope": "aggregate_results"
      },
      "fragment_argument_access_surface": "args.name",
      "surface_kind": "step_form"
    },
    "step_form_rules": [
      {
        "fields": [
          "uses",
          "run",
          "steps",
          "profile_switch",
          "value",
          "result",
          "publish",
          "state_set",
          "state_delete"
        ],
        "kind": "exclusive_choice",
        "message": "A workflow step must define exactly one of uses, run, steps, profile_switch, value, result, publish, state_set, or state_delete",
        "name": "exactly_one_step_form"
      },
      {
        "field": "with",
        "kind": "dependency",
        "message": "The with field is allowed only together with uses or run",
        "name": "with_requires_uses",
        "requires": [
          "uses",
          "run"
        ]
      },
      {
        "field": "for_each",
        "kind": "dependency",
        "message": "The for_each field is allowed only together with run or inline steps",
        "name": "for_each_requires_invocation_body",
        "requires": [
          "run",
          "steps"
        ]
      },
      {
        "field": "steps",
        "kind": "dependency",
        "message": "Inline repeated step bodies require for_each",
        "name": "inline_steps_require_for_each",
        "requires": [
          "for_each"
        ]
      }
    ],
    "step_forms": [
      {
        "deprecated_optional_fields": [
          "launcher"
        ],
        "if_expression_surface": "native_local_expression_preferred_embedded_deprecated",
        "name": "operation_call",
        "optional_fields": [
          "if",
          "with",
          "register",
          "launcher"
        ],
        "preferred_alternatives": {
          "launcher": "routine_or_profile_context"
        },
        "required_fields": [
          "name",
          "uses"
        ]
      },
      {
        "if_expression_surface": "native_local_expression_preferred_embedded_deprecated",
        "name": "run_invocation",
        "optional_fields": [
          "if",
          "with",
          "for_each",
          "register"
        ],
        "required_fields": [
          "name",
          "run"
        ]
      },
      {
        "if_expression_surface": "native_local_expression_preferred_embedded_deprecated",
        "name": "inline_fan_out_invocation",
        "optional_fields": [
          "if",
          "register"
        ],
        "required_fields": [
          "name",
          "for_each",
          "steps"
        ]
      },
      {
        "if_expression_surface": "native_local_expression_preferred_embedded_deprecated",
        "name": "profile_switch",
        "optional_fields": [
          "if"
        ],
        "required_fields": [
          "name",
          "profile_switch"
        ]
      },
      {
        "if_expression_surface": "native_local_expression_preferred_embedded_deprecated",
        "name": "value",
        "optional_fields": [
          "if",
          "register"
        ],
        "required_fields": [
          "name",
          "value"
        ]
      },
      {
        "if_expression_surface": "native_local_expression_preferred_embedded_deprecated",
        "name": "result",
        "optional_fields": [
          "if"
        ],
        "required_fields": [
          "name",
          "result"
        ]
      },
      {
        "if_expression_surface": "native_local_expression_preferred_embedded_deprecated",
        "name": "publish",
        "optional_fields": [
          "if"
        ],
        "required_fields": [
          "name",
          "publish"
        ]
      },
      {
        "if_expression_surface": "native_local_expression_preferred_embedded_deprecated",
        "name": "state_set",
        "optional_fields": [
          "if"
        ],
        "required_fields": [
          "name",
          "state_set"
        ]
      },
      {
        "if_expression_surface": "native_local_expression_preferred_embedded_deprecated",
        "name": "state_delete",
        "optional_fields": [
          "if"
        ],
        "required_fields": [
          "name",
          "state_delete"
        ]
      }
    ],
    "surface_constraints": {
      "guard_expression": {
        "allowed_builtins": [
          "format",
          "is_missing",
          "is_present"
        ],
        "allowed_filters": [
          "lower",
          "trim",
          "slug",
          "eq",
          "ne",
          "not",
          "is_string",
          "is_number",
          "is_integer",
          "is_boolean",
          "in",
          "field",
          "flatten",
          "first",
          "last",
          "length",
          "unique"
        ],
        "allowed_roots": [
          "inputs",
          "probe",
          "state"
        ],
        "boolean_operators": [
          "and",
          "or",
          "not",
          "parentheses"
        ],
        "representation_adapter_policy": {
          "forbidden_write_surface": "->...",
          "read_only_allowed": true,
          "write_paths_forbidden": true
        },
        "result_contract": {
          "non_boolean_result": "error",
          "required_output_type": "boolean"
        }
      },
      "runtime_value_surface": {
        "allowed_builtins": [
          "format",
          "is_missing",
          "is_present"
        ],
        "allowed_filters": [
          "lower",
          "trim",
          "slug",
          "eq",
          "ne",
          "not",
          "is_string",
          "is_number",
          "is_integer",
          "is_boolean",
          "in",
          "field",
          "flatten",
          "first",
          "last",
          "length",
          "unique"
        ],
        "allowed_roots": [
          "inputs",
          "args",
          "state",
          "step"
        ],
        "boolean_operators": [
          "and",
          "or",
          "not",
          "parentheses"
        ]
      }
    },
    "top_level_fields": [
      {
        "name": "version",
        "required": true,
        "type": "integer"
      },
      {
        "name": "workflow",
        "required": true,
        "type": "string"
      },
      {
        "activation_requirement": "all_declared_keys_required",
        "authoring_role": "declares_global_activation_inputs",
        "name": "inputs",
        "required": false,
        "type": "object",
        "unknown_input_policy": "reject_unknown_inputs"
      },
      {
        "authoring_role": "declares_workflow_local_named_expressions",
        "name": "let",
        "required": false,
        "type": "object"
      },
      {
        "name": "state_needs",
        "required": false,
        "type": "object"
      },
      {
        "name": "blocks",
        "required": false,
        "type": "array"
      }
    ],
    "version": 0
  }
}
```
