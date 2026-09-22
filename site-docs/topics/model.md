# Workflow model

This page outlines the main workflow contracts used in workflows, playbooks, profiles, and runtime state.

Use this page when you need field-level workflow contract details.

## Full JSON reference

```json
{
  "connector_authoring_guidance": "Connector-author SDK: ctx.call(name, *, inputs=None) supports nonempty already-resolved inputs only for same-family probe dependencies. Full references (gh.pr.list) and local dotted names (pr.list) work; values are not reevaluated as expressions or templates. Omitted inputs or None preserve legacy no-input behavior. Cross-family calls and probe-to-action hidden mutation are rejected; no new action composition. Inspect connector.authoring for dependency boundaries and verified examples.",
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
                "branch": "string",
                "force": "boolean"
              },
              "reference": "git.branch.delete"
            }
          ],
          "failure_modes": [
            "input_error",
            "branch_not_found",
            "branch_checked_out",
            "default_branch_protected",
            "branch_not_merged",
            "delete_blocked"
          ],
          "inputs": {
            "branch": "string",
            "force": "boolean"
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
          "summary": "Delete a local non-default branch; optional boolean force defaults to false (-d), true uses -D.",
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
          "summary": "Return a bounded readable list of commit texts from one revision scope with only minimal metadata. rev accepts revisions and ranges such as HEAD~10..HEAD, not Git options; after trimming whitespace it must not start with '-'. This probe is intentionally narrow: it does not expose patch text, changed files, diff stats, graph decoration, or arbitrary git log formatting.",
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
              "inputs": {
                "remote": "string"
              },
              "reference": "git.remote"
            }
          ],
          "failure_modes": [
            "probe_failed"
          ],
          "inputs": {
            "remote": "string"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "remote",
          "outputs": {
            "exists": "boolean",
            "fetch_urls": [
              "string"
            ],
            "mirror": "boolean | null",
            "name": "string",
            "push_urls": [
              "string"
            ]
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Inspect a configured remote's effective fetch and push URLs and mirror setting without network access. Git applies URL rewrites; returned URLs are preserved verbatim. An absent remote has exists=false, empty URL lists, and mirror=null.",
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
          "summary": "Fetch from a configured remote name, not a direct URL, path, or option",
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
          "summary": "Push to a configured remote name; omitted or null remote uses the upstream-derived name, validated against configured names",
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
                "name": "v1.2.3"
              },
              "reference": "git.tag"
            },
            {
              "inputs": {
                "name": "release-2026-07"
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
          "summary": "Read one Git tag. The `oid` output is the object id resolved for the tag ref itself; for annotated tags this is the tag object's oid rather than the peeled target commit oid.",
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
                "match": "v*",
                "match_kind": "glob"
              },
              "reference": "git.tags"
            },
            {
              "inputs": {
                "match": "^v?[0-9]+\\.[0-9]+\\.[0-9]+$",
                "match_kind": "regex"
              },
              "reference": "git.tags"
            }
          ],
          "failure_modes": [
            "probe_failed"
          ],
          "inputs": {
            "match": "string | null",
            "match_kind": "'glob' | 'regex' | null"
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
          "summary": "Inspect Git tags sorted by descending version refname. Each returned `oid` is the peeled target object id; for annotated tags this means the referenced object oid rather than the tag object oid. The `latest` output is the first matching item in that version-sorted order, not the newest tag by creation date.",
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
          "summary": "Inspect the exact configured upstream remote, including nested names, and its conventional local tracking-tail branch",
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
          "project_directory",
          "compose_file",
          "project_name"
        ],
        "prerequisites": [
          "docker compose available"
        ]
      },
      "namespace": "compose",
      "operations": [
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {},
              "reference": "compose.project"
            }
          ],
          "failure_modes": [
            "project_invalid",
            "orchestrator_unavailable",
            "observation_failed"
          ],
          "inputs": {},
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "project",
          "outputs": {
            "declared_services": "array[string]",
            "project": "string",
            "service_counts": "object",
            "services": "object",
            "state": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Observe one Compose project as an orchestration unit.",
          "tags": [
            "compose",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [
            "remove the materialized runtime instance for one Compose service"
          ],
          "examples": [
            {
              "inputs": {
                "service": "string"
              },
              "reference": "compose.remove"
            }
          ],
          "failure_modes": [
            "service_not_declared",
            "service_running",
            "project_invalid",
            "orchestrator_unavailable",
            "runtime_remove_failed",
            "remove_failed"
          ],
          "inputs": {
            "service": "string"
          },
          "invalidates_observations": [
            "compose.*"
          ],
          "kind": "action",
          "maturity": "stable",
          "name": "remove",
          "outputs": {
            "changed": "boolean",
            "state": "string",
            "target": "string",
            "target_kind": "string"
          },
          "preflight_observations": [
            {
              "probe": "compose.service",
              "with": {
                "service": "{service}"
              }
            }
          ],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Remove one stopped materialized Compose service instance.",
          "tags": [
            "compose",
            "action"
          ]
        },
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {
                "service": "api"
              },
              "reference": "compose.service"
            }
          ],
          "failure_modes": [
            "service_not_declared",
            "project_invalid",
            "orchestrator_unavailable",
            "observation_failed"
          ],
          "inputs": {
            "service": "string"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "service",
          "outputs": {
            "containers": "object",
            "declared": "boolean",
            "healthy": "boolean | null",
            "published_ports": "array[string]",
            "service": "string",
            "state": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Observe one declared Compose service as an orchestration unit.",
          "tags": [
            "compose",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [
            "bring the requested Compose target into operational running state"
          ],
          "examples": [
            {
              "inputs": {
                "service": "string | null"
              },
              "reference": "compose.start"
            }
          ],
          "failure_modes": [
            "service_not_declared",
            "project_invalid",
            "orchestrator_unavailable",
            "image_unavailable",
            "build_failed",
            "dependency_failed",
            "runtime_start_failed",
            "healthcheck_failed",
            "start_failed"
          ],
          "inputs": {
            "service": "string | null"
          },
          "invalidates_observations": [
            "compose.*"
          ],
          "kind": "action",
          "maturity": "stable",
          "name": "start",
          "outputs": {
            "changed": "boolean",
            "changed_services": "array[string]",
            "state": "string",
            "target": "string",
            "target_kind": "string"
          },
          "preflight_observations": [
            {
              "probe": "compose.project",
              "with": {}
            }
          ],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Bring one Compose project or service into operational running state.",
          "tags": [
            "compose",
            "action"
          ]
        },
        {
          "deprecated": false,
          "effects": [
            "stop the requested Compose target"
          ],
          "examples": [
            {
              "inputs": {
                "service": "string | null"
              },
              "reference": "compose.stop"
            }
          ],
          "failure_modes": [
            "service_not_declared",
            "project_invalid",
            "orchestrator_unavailable",
            "dependency_stop_blocked",
            "runtime_stop_failed",
            "stop_failed"
          ],
          "inputs": {
            "service": "string | null"
          },
          "invalidates_observations": [
            "compose.*"
          ],
          "kind": "action",
          "maturity": "stable",
          "name": "stop",
          "outputs": {
            "changed": "boolean",
            "changed_services": "array[string]",
            "state": "string",
            "target": "string",
            "target_kind": "string"
          },
          "preflight_observations": [
            {
              "probe": "compose.project",
              "with": {}
            }
          ],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Stop one Compose project or service.",
          "tags": [
            "compose",
            "action"
          ]
        }
      ]
    },
    {
      "bootstrap": {
        "context_fields": [
          "host",
          "viewer",
          "scopes",
          "repository"
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
                "attempt": "integer",
                "check_suite_id": "integer",
                "repository": "string",
                "run_id": "integer"
              },
              "reference": "gh.actions.run"
            }
          ],
          "failure_modes": [
            "input_error",
            "actions_run_unavailable"
          ],
          "inputs": {
            "attempt": "integer",
            "check_suite_id": "integer",
            "repository": "string",
            "run_id": "integer"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "actions.run",
          "outputs": {
            "check_suite_id": "integer",
            "conclusion": "string",
            "created_at": "string",
            "event": "string",
            "found": "boolean",
            "head_branch": "string",
            "head_sha": "string",
            "pull_requests": [
              {
                "base_sha": "string",
                "head_sha": "string",
                "number": "integer"
              }
            ],
            "repository": "string",
            "run_attempt": "integer",
            "run_id": "integer",
            "run_started_at": "string",
            "status": "string",
            "updated_at": "string",
            "url": "string",
            "workflow_id": "integer",
            "workflow_path": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Observe an exact Actions attempt by run or check suite; omitted attempt pins the latest observed attempt. PR SHAs are API observations, not immutable event snapshots.",
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
                "attempt": "integer",
                "repository": "string",
                "run_id": "integer"
              },
              "reference": "gh.actions.run.jobs"
            }
          ],
          "failure_modes": [
            "input_error",
            "actions_jobs_unavailable"
          ],
          "inputs": {
            "attempt": "integer",
            "repository": "string",
            "run_id": "integer"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "actions.run.jobs",
          "outputs": {
            "complete": "boolean",
            "count": "integer",
            "items": [
              {
                "check_run_id": "integer",
                "completed_at": "string",
                "conclusion": "string",
                "head_sha": "string",
                "job_id": "integer",
                "name": "string",
                "started_at": "string",
                "status": "string",
                "url": "string"
              }
            ],
            "repository": "string",
            "run_attempt": "integer",
            "run_id": "integer"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Observe all jobs for an exact Actions run attempt; fail on incomplete or inconsistent pagination.",
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
                "pull_number": 42
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
            "base_repository": "string",
            "base_sha": "string",
            "body": "string",
            "changed_files": "integer",
            "commits_count": "integer",
            "created_at": "string",
            "deletions": "integer",
            "draft": "boolean",
            "head_ref": "string",
            "head_repository": "string",
            "head_sha": "string",
            "merge_commit_sha": "string",
            "mergeable": "boolean",
            "mergeable_state": "string",
            "merged": "boolean",
            "merged_at": "string",
            "number": "integer",
            "repository": "string",
            "review_decision": "string",
            "stack": "object",
            "stack_state": "string",
            "state": "string",
            "test_merge_base_sha": "string",
            "test_merge_head_sha": "string",
            "test_merge_reason": "string",
            "test_merge_sha": "string",
            "test_merge_state": "string",
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
                "expected_head_sha": "string",
                "pull_number": "integer",
                "repository": "string",
                "target": "string"
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
            "expected_head_sha": "string",
            "pull_number": "integer",
            "repository": "string",
            "target": "string"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "pr.checks",
          "outputs": {
            "base_repository": "string",
            "base_sha": "string",
            "check_runs_complete": "boolean",
            "checks": [
              {
                "app_id": "integer",
                "app_identity": "string",
                "app_slug": "string",
                "check_suite_id": "integer",
                "completed_at": "string",
                "conclusion": "string",
                "context": "string",
                "created_at": "string",
                "creator": "object",
                "id": "integer",
                "kind": "string",
                "name": "string",
                "sha": "string",
                "sha_source": "string",
                "started_at": "string",
                "state": "string",
                "status": "string",
                "updated_at": "string",
                "url": "string"
              }
            ],
            "commit_sha": "string",
            "complete": "boolean",
            "expected_head_sha": "string",
            "failed_count": "integer",
            "head_repository": "string",
            "head_sha": "string",
            "neutral_count": "integer",
            "overall_state": "string",
            "pending_count": "integer",
            "pull_ref": "string",
            "sha_evidence": "string",
            "skipped_count": "integer",
            "statuses_complete": "boolean",
            "success_count": "integer",
            "target": "string",
            "test_merge_base_sha": "string",
            "test_merge_head_sha": "string",
            "test_merge_reason": "string",
            "test_merge_sha": "string",
            "test_merge_state": "string",
            "total_count": "integer",
            "unknown_count": "integer"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Observe paginated API-attached checks for a PR head or verified test merge; optionally bind expected_head_sha.",
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
          "effects": [
            "create one GitHub pull request after a non-atomic open duplicate precheck"
          ],
          "examples": [
            {
              "inputs": {
                "base": "string",
                "body": "string",
                "draft": "boolean",
                "head": "string",
                "head_owner": "string",
                "head_repository": "string",
                "repository": "string",
                "title": "string"
              },
              "reference": "gh.pr.create"
            }
          ],
          "failure_modes": [
            "input_error",
            "precheck_failed",
            "ambiguous",
            "already_exists",
            "api_failed",
            "create_refused",
            "creation_unknown"
          ],
          "inputs": {
            "base": "string",
            "body": "string",
            "draft": "boolean",
            "head": "string",
            "head_owner": "string",
            "head_repository": "string",
            "repository": "string",
            "title": "string"
          },
          "invalidates_observations": [
            "gh.*"
          ],
          "kind": "action",
          "maturity": "stable",
          "name": "pr.create",
          "outputs": {
            "base_ref": "string | null",
            "base_repository": "string | null",
            "base_sha": "string | null",
            "created": "boolean | null",
            "draft": "boolean | null",
            "errors": "array | object | string | null",
            "head_ref": "string | null",
            "head_repository": "string | null",
            "head_sha": "string | null",
            "http_status": "integer | null",
            "message": "string | null",
            "pull_number": "integer | null",
            "pull_ref": "string | null",
            "repository": "string | null",
            "state": "string | null",
            "url": "string | null"
          },
          "preflight_observations": [
            {
              "fields": [
                "items",
                "count",
                "complete"
              ],
              "probe": "gh.pr.list",
              "with": {
                "base": "{base}",
                "head": "{head}",
                "repository": "{repository}",
                "state": "open"
              }
            }
          ],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Create one PR with explicit draft and exact source repository after a complete gh.pr.list open guard; creation_unknown must not be blindly retried.",
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
                "pull_number": 42
              },
              "reference": "gh.pr.diff"
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
          "name": "pr.diff",
          "outputs": {
            "files": [
              "object"
            ],
            "pull_ref": "string",
            "total_files": "integer"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Read normalized change content from a GitHub pull request.",
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
                "base": "string",
                "head": "string",
                "head_owner": "string",
                "repository": "string",
                "state": "string"
              },
              "reference": "gh.pr.list"
            }
          ],
          "failure_modes": [
            "input_error",
            "pull_list_unavailable"
          ],
          "inputs": {
            "base": "string",
            "head": "string",
            "head_owner": "string",
            "repository": "string",
            "state": "string"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "pr.list",
          "outputs": {
            "base": "string",
            "complete": "boolean",
            "count": "integer",
            "head": "string",
            "head_owner": "string",
            "items": [
              {
                "base_ref": "string",
                "base_repository": "string",
                "base_sha": "string",
                "draft": "boolean",
                "head_owner": "string",
                "head_ref": "string",
                "head_repository": "string",
                "head_repository_key": "string",
                "head_sha": "string",
                "merged": "boolean",
                "merged_at": "string",
                "number": "integer",
                "pull_ref": "string",
                "state": "string",
                "url": "string"
              }
            ],
            "repository": "string",
            "state": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "List GitHub.com REST pull requests by explicit state (open|closed|all) and optional branches; bare head is filtered locally across all pages. Complete traversal is not an atomic snapshot.",
          "tags": [
            "gh",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [
            "submit a direct asynchronous GitHub merge after observing a standalone PR; stack/base observation is not atomic"
          ],
          "examples": [
            {
              "inputs": {
                "expected_head_sha": "6358cd125586d9def8c3e5943f23506202da81cc",
                "merge_method": "squash",
                "pull_number": 42,
                "repository": "octocat/Hello-World"
              },
              "reference": "gh.pr.merge"
            }
          ],
          "failure_modes": [
            "input_error",
            "unsupported_stack",
            "merge_scope_unknown",
            "head_mismatch",
            "merge_api_failed",
            "merge_refused",
            "existing_request_conflict",
            "existing_request_unknown",
            "merge_result_unknown"
          ],
          "inputs": {
            "expected_head_sha": "string",
            "merge_method": "string",
            "pull_number": "integer",
            "repository": "string"
          },
          "invalidates_observations": [
            "gh.pr.*",
            "gh.issue",
            "gh.project.issue"
          ],
          "kind": "action",
          "maturity": "stable",
          "name": "pr.merge",
          "outputs": {
            "expected_head_sha": "string",
            "http_status": "integer",
            "merge_action": "string",
            "merge_method": "string",
            "merge_sha": "string",
            "merged": "boolean",
            "message": "string",
            "observed_head_sha": "string",
            "pull_number": "integer",
            "repository": "string",
            "request_compatibility": "string",
            "request_id": "string",
            "stack_scope": "string",
            "state": "string",
            "submission": "string"
          },
          "preflight_observations": [
            {
              "fields": [
                "state",
                "draft",
                "head_sha",
                "stack_state"
              ],
              "probe": "gh.pr",
              "with": {
                "pull_number": "{pull_number}",
                "repository": "{repository}"
              }
            }
          ],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Request a SHA-guarded direct async merge; save request_id for gh.pr.merge.request. Acceptance is not completion.",
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
                "repository": "octocat/Hello-World",
                "request_id": "12345678-1234-1234-1234-123456789abc"
              },
              "reference": "gh.pr.merge.request"
            }
          ],
          "failure_modes": [
            "input_error",
            "request_unavailable"
          ],
          "inputs": {
            "pull_number": "integer",
            "repository": "string",
            "request_id": "string"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "pr.merge.request",
          "outputs": {
            "expected_head_sha": "string",
            "http_status": "integer",
            "merge_action": "string",
            "merge_method": "string",
            "merge_sha": "string",
            "merged": "boolean",
            "message": "string",
            "pull_number": "integer",
            "repository": "string",
            "request_id": "string",
            "state": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Observe a saved async merge UUID once: pending, merged, enqueued, or failed. Requests expire after 24 hours; 404 is unavailable, not failure proof.",
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
        },
        {
          "deprecated": false,
          "effects": [],
          "examples": [
            {
              "inputs": {},
              "reference": "gh.repo"
            }
          ],
          "failure_modes": [
            "repository_not_found",
            "probe_failed"
          ],
          "inputs": {
            "repository": "string"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "repo",
          "outputs": {
            "archived": "boolean",
            "default_branch": "string | null",
            "id": "string",
            "is_fork": "boolean",
            "parent_repository": "string | null",
            "repository": "string"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Read normalized GitHub repository identity and fork facts.",
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
              "inputs": {},
              "reference": "gh.repo.actions.permissions"
            }
          ],
          "failure_modes": [
            "repository_not_found",
            "probe_failed"
          ],
          "inputs": {
            "repository": "string"
          },
          "invalidates_observations": [],
          "kind": "probe",
          "maturity": "stable",
          "name": "repo.actions.permissions",
          "outputs": {
            "allowed_actions": "string | null",
            "enabled": "boolean",
            "repository": "string",
            "sha_pinning_required": "boolean | null"
          },
          "preflight_observations": [],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Read GitHub Actions permissions for one repository.",
          "tags": [
            "gh",
            "probe"
          ]
        },
        {
          "deprecated": false,
          "effects": [
            "set the GitHub Actions enabled state for one repository"
          ],
          "examples": [
            {
              "inputs": {
                "enabled": false
              },
              "reference": "gh.repo.actions.permissions.set"
            }
          ],
          "failure_modes": [
            "repository_not_found",
            "set_blocked"
          ],
          "inputs": {
            "enabled": "boolean",
            "repository": "string"
          },
          "invalidates_observations": [],
          "kind": "action",
          "maturity": "stable",
          "name": "repo.actions.permissions.set",
          "outputs": {
            "changed": "boolean",
            "enabled": "boolean",
            "repository": "string"
          },
          "preflight_observations": [
            {
              "fields": [
                "enabled"
              ],
              "probe": "gh.repo.actions.permissions",
              "with": {}
            }
          ],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Set the GitHub Actions enabled state for one repository.",
          "tags": [
            "gh",
            "action"
          ]
        },
        {
          "deprecated": false,
          "effects": [
            "sync one fork repository default branch from its parent repository"
          ],
          "examples": [
            {
              "inputs": {},
              "reference": "gh.repo.sync"
            }
          ],
          "failure_modes": [
            "repository_not_found",
            "not_a_fork",
            "archived_repository",
            "default_branch_unavailable",
            "sync_blocked"
          ],
          "inputs": {
            "repository": "string"
          },
          "invalidates_observations": [],
          "kind": "action",
          "maturity": "stable",
          "name": "repo.sync",
          "outputs": {
            "branch": "string",
            "repository": "string",
            "synced": "boolean",
            "upstream_repository": "string"
          },
          "preflight_observations": [
            {
              "fields": [
                "is_fork",
                "default_branch",
                "parent_repository",
                "archived"
              ],
              "probe": "gh.repo",
              "with": {}
            }
          ],
          "prerequisites": [],
          "replaced_by": [],
          "summary": "Sync one GitHub fork repository default branch from its parent repository.",
          "tags": [
            "gh",
            "action"
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
            "basename": "string",
            "content": "string",
            "exists": "boolean",
            "extension": "string",
            "filename_without_extension": "string",
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
          "summary": "Read canonical content and metadata from the same opened regular file, without atomic snapshot guarantees.",
          "tags": [
            "fs",
            "probe"
          ]
        }
      ]
    }
  ],
  "document_kind": "model",
  "gh_pr_create_guidance": "GitHub creation: gh.pr.create requires head, base, title, and an explicit boolean draft; body defaults to empty. repository is optional: valid explicit OWNER/REPO overrides connector_contexts.gh.repository; omitted or null uses context, malformed explicit input fails without fallback. head_repository is a full source OWNER/REPO, default target repository; explicit cross-repository intent requires it, with no fork guessing. head_owner is an optional consistency assertion, otherwise derived from the exact source repository. Same-organization head_repo API argument is derived repository NAME. Reject same-branch/same-repository requests. The action uses ctx.call('gh.pr.list', inputs=...) with resolved repository/head/head_owner/base and state: open; require complete traversal and exact case-insensitive head_repository_key identity. One exact open match including draft returns non-OK already_exists with pull_number, url, created=false and no POST; multiple matches return ambiguous; unknown identity and list failure return precheck_failed. No existing match permits one POST. Only validated HTTP 201 means created=true; malformed 201, timeout, or server failure returns creation_unknown with created=null. HTTP 422 is generic create_refused, not universal duplicate evidence; preserve API errors. No POST retry or automatic readback reconciliation. This is not find-or-reuse or closed-history policy: workflow-owned gh.pr.list state: all classification precedes create's separate open check. Concurrent duplicates can race the check: no atomic uniqueness or exactly-once guarantee. No CI waiting, merge, push, fork, branch cleanup, or extra issue/project operations. Inspect connector.gh.pr.create.",
  "gh_pr_merge_guidance": "GitHub async merge: gh.pr observes head/base/test-merge identity and stack_state (standalone/stacked/unknown) plus stack; gh.pr.checks observes CI evidence. gh.pr.merge requires expected_head_sha from the accepted CI head, never a freshly fetched replacement. For gh.pr.merge and gh.pr.merge.request, repository is optional: a valid explicit OWNER/REPO overrides the bootstrapped connector_contexts.gh.repository; omitted or null uses that context. Malformed explicit values fail without fallback, and no resolved repository is an error. For checks on candidate M with verified base B and head H, submit expected_head_sha=H, not M. The first version rejects stacked PRs and unknown scope before submission; there is no atomic base or stack guarantee. Save the action result request_id UUID for gh.pr.merge.request: accepted submission is not completion. Observe pending/merged/failed/enqueued once; unavailable is not failed and enqueued is not merged. Only an exact matching existing request is reusable. No polling, queue administration, or admin bypass is provided. GitHub automatic issue closing and branch configuration effects are outside this action. Inspect connector.gh.pr.merge and connector.gh.pr.merge.request for the verified canonical workflow example.",
  "graph_context": "Graph does not read saved state, run probes, or recommend what to do next. Use workflows show <workflow> for inputs, check <workflow> to check whether it can run, explain <workflow> to understand why, and next for a recommendation in the current environment.",
  "graph_guidance": "Show how workflows connect through persistent state. Use ordo-playbook graph to explore related workflows, where they write shared data, and where that data is removed. No active task is required.",
  "graph_parameters": "parameter stands for a key that has not been selected; the relationship applies to a matching context instance. Use graph --json for detailed dependencies, conditions, and unresolved relationships. Technical reference: docs/static-graph.md and meta/model/runtime/graph-v1.md.",
  "graph_presentation": "Read +field as a write, −field as a deletion, and ? as a conditional change. A write need not be the first write; −context removes the selected context.",
  "graph_roles": "↔ marks the same workflow: state/kind identifies another role; (reference) is a leaf sighting, not another execution. A deletion appears near the related data's users; this does not require running every reader before deleting the data.",
  "graph_source_placement": "Shared context: writers → readers, not execution order. A free reader root is marked (data use; alternative sources) because it uses data without mutating the context. This shows shared data, not a mandatory sequence: guards and check determine applicability, and alternative ends are not sequential steps. Playbook order helps arrange workflows when their relationships leave a choice. Writers and deletions can also be branches. When sources already form a chain, the deepest source is the parent; also reads from keeps other sources visible. Distinct data from incomparable sources is shown under each source: the first source in display order holds the full occurrence, and ↔ (reference) leaves show the same operation without repeating its subtree. Alternative writers of the same data stay together. reads from: name? marks known conditional or fallback data use, separately from +field?. Fallback reads still count as data use. A missing graph edge does not prove independence in external systems.",
  "local_expressions": {
    "builtins": [
      {
        "allowed_roots": [
          "args",
          "inputs",
          "probe",
          "state",
          "step"
        ],
        "name": "format",
        "summary": "Published local-expression builtin for inline workflow expressions."
      },
      {
        "allowed_roots": [
          "args",
          "inputs",
          "probe",
          "state",
          "step"
        ],
        "name": "is_missing",
        "summary": "Published local-expression builtin for inline workflow expressions."
      },
      {
        "allowed_roots": [
          "args",
          "inputs",
          "probe",
          "state",
          "step"
        ],
        "name": "is_present",
        "summary": "Published local-expression builtin for inline workflow expressions."
      }
    ],
    "condition_structures": {
      "equal_authority_if_forms": [
        "expression_string",
        "structured_condition"
      ],
      "list_semantics": "implicit_all",
      "structured_operators": [
        "all",
        "any",
        "not"
      ]
    },
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
        "argument_count": 1,
        "input_type": "json",
        "name": "lookup",
        "output_type": "json"
      },
      {
        "argument_count": 1,
        "authored_form": "only(field=value) / only(field!=value)",
        "input_type": "json",
        "name": "only",
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
      },
      {
        "argument_count": 2,
        "authored_form": "catch([\"issue_not_found\", \"*_not_found\"], false)",
        "input_type": "json",
        "name": "catch",
        "output_type": "json"
      },
      {
        "argument_count": 0,
        "input_type": "json",
        "name": "not_found",
        "output_type": "boolean"
      }
    ]
  },
  "playbook": {
    "activation_semantics": {
      "connector_context": {
        "consumer": "connector_bootstrap",
        "family_entry_type": "object",
        "profile_refinement": true,
        "top_level_field": "connectors"
      },
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
          "with",
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
          "with",
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
        "documentation_role": "playbook_owned_pre_run_invocation_inputs",
        "name": "with",
        "required": false,
        "runtime_effect": "supplies_playbook_owned_pre_run_inputs",
        "type": "object",
        "value_surface": "static_yaml_values_only"
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
        "name": "connectors",
        "required": false,
        "runtime_effect": "supplies_raw_connector_bootstrap_input",
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
        "caller_slot_forms": [
          {
            "meaning": "caller_must_supply_input_via_cli_or_activation_override",
            "shape": "key:"
          },
          {
            "meaning": "caller_may_supply_input_via_cli_or_activation_override",
            "shape": "key?:"
          }
        ],
        "name": "with",
        "required": false,
        "runtime_effect": "supplies_playbook_owned_workflow_entry_inputs_or_declares_required_or_optional_caller_slots",
        "type": "object",
        "value_surface": "static_yaml_values_or_blank_required_slots_or_blank_optional_question_suffix_slots"
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
      "connectors": {
        "conflict": "validation_error",
        "conflict_key": "family_field",
        "strategy": "shallow_merge_by_family"
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
        "name": "connectors",
        "required": false,
        "runtime_effect": "supplies_raw_connector_bootstrap_input",
        "type": "object"
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
      "connectors": {
        "consumer": "connector_bootstrap",
        "mutates_workflow_steps": false,
        "published_as_explicit_metadata": false
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
        "actions": [
          "set",
          "remove"
        ],
        "name": "json",
        "selectors": [
          ".field",
          "[\"literal-key\"]",
          "[n]",
          "..field",
          ".one(field=value)",
          ".many(field=value)",
          ".one(field!=value)",
          ".many(field!=value)"
        ],
        "shortcuts": [],
        "summary": "Select values from strict JSON text through exact structural paths."
      },
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
      },
      {
        "actions": [],
        "name": "yaml",
        "selectors": [
          ".field",
          "[\"literal-key\"]",
          "[n]",
          ".one(field=value)",
          ".one(field!=value)",
          ".many(field=value)",
          ".many(field!=value)"
        ],
        "shortcuts": [],
        "summary": "Select values from one YAML document through exact structural paths and immediate-child filters."
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
  "routine_contract": {
    "authoring_guidance": {
      "avoid_when": "the remaining gap is semantic or a reusable connector model should exist instead",
      "default_recommendation": "avoid_by_default",
      "not_a_connector_family": true,
      "role": "bounded_project_local_opaque_automation",
      "use_when": "no richer public surface exists and the remaining gap is mechanical or intentionally project-local"
    },
    "authoring_status": "exception_path",
    "discovery": {
      "path": ".ordo/routines.yaml"
    },
    "document_kind": "routine_registry",
    "implementation_fields": [
      {
        "authoring_status": "bounded_execution_only",
        "name": "argv",
        "required": true,
        "type": "array"
      }
    ],
    "routine_entry_fields": [
      {
        "authoring_status": "exception_path",
        "name": "kind",
        "required": true,
        "type": "string"
      },
      {
        "name": "summary",
        "required": true,
        "type": "string"
      },
      {
        "name": "args",
        "required": false,
        "type": "object"
      },
      {
        "name": "implementation",
        "required": true,
        "type": "object"
      },
      {
        "name": "failure_modes",
        "required": true,
        "type": "array"
      },
      {
        "name": "outputs",
        "required": false,
        "type": "object"
      },
      {
        "name": "log_hints",
        "required": false,
        "type": "object"
      }
    ],
    "top_level_fields": [
      {
        "name": "version",
        "required": true,
        "type": "integer"
      },
      {
        "name": "routines",
        "required": true,
        "type": "object"
      }
    ],
    "version": 1,
    "workflow_call_surface": {
      "automatic_input_env_projection": false,
      "env_non_scalar_behavior": "execution_error",
      "env_reference_pattern": "supported_reference_path_only",
      "env_reference_roots": [
        "inputs",
        "step",
        "state"
      ],
      "env_scalar_only": true,
      "fields": [
        {
          "name": "args",
          "required": false,
          "role": "declared_business_arguments",
          "type": "object"
        },
        {
          "name": "env",
          "required": false,
          "role": "explicit_forwarded_scalar_context_references",
          "type": "list[string]"
        }
      ],
      "generated_env_name_examples": {
        "inputs.profile": "ORDO_INPUTS_PROFILE",
        "step.collect.outputs.value.path": "ORDO_STEP_COLLECT_OUTPUTS_VALUE_PATH"
      },
      "generated_env_name_prefix": "ORDO_"
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
        "message": "state path key expression must be a valid local expression",
        "name": "key_expression_must_be_valid_local_expression"
      },
      {
        "message": "state path must not contain trailing content",
        "name": "no_trailing_content"
      }
    ],
    "path_forms": {
      "key_expression_surface": "embedded_value_expression",
      "root": "state",
      "shape": "state.<role>[<expression>][.<field>...]",
      "supports_hyphenated_roles": true,
      "supports_nested_fields": true
    },
    "preflight": {
      "boundary": "Nested analysis does not defer mutations. A reached run or loop after deferral halts with state_deferral_invocation_barrier; profile switches cannot resume that barrier.",
      "classification": "effectful",
      "planning": "Retain ordered nodes with reuse_policy not_reusable and planned_probe_result null; execute admitted mutations once in order, with divergence_status not_applicable for deferred nodes.",
      "rule": "Check conditions and gates first, then defer eligible top-level mutations without mutation, simulation, outputs, registers, or reusable observations; continue to independent guards.",
      "top_level_status": "deferred",
      "verification_scope": "Validate individual workflows and children, not flattened caller-child access streams. Cross-invocation and cross-iteration guarantees remain deferred; this is not a full composed-run or cross-run proof."
    },
    "runtime_rules": [
      {
        "error_code": "validation.workflow.state_role.write_before_last_read",
        "message": "Before binding, authoring validation requires writes or deletes of a logical state role only after its final read, regardless of key or field. Bound validation instead compares actual storage in each access context. Use step registers for per-run dataflow.",
        "name": "write_after_last_read"
      },
      {
        "error_code": "validation.workflow.state_storage.write_before_last_read",
        "message": "After binding, write or delete only after the final read of the same actual file, regardless of role, state name, profile, key, or field. Resolve relative paths in each access context; normalized paths, symlinks, and existing hardlinks can alias. The same role may access different files and be valid.",
        "name": "bound_storage_write_after_last_read"
      },
      {
        "error_code": "validation.workflow.state_storage.identity_unresolved",
        "message": "Conservatively reject early only relevant write/later-read pairs whose storage identity cannot be established without execution or observations. This is not a proven ordering violation; uncertain context alone does not reject read-only, read-before-write, or known-disjoint access. Cross-invocation and cross-iteration guarantees remain deferred, without a new loop mutation ban.",
        "name": "relevant_storage_identity_required"
      },
      {
        "error_code": "runtime.state.binding_missing",
        "message": "state role must be bound before runtime access",
        "name": "bound_role_required"
      },
      {
        "error_code": "runtime.state.key_invalid",
        "message": "state key expression must resolve to a non-null scalar value",
        "name": "non_null_scalar_key_required"
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
      "step_scope": "shared_across_assembled_workflow_after_include_expansion",
      "stops_on_first_match": true,
      "targets": "files_only",
      "validation_boundary": "assembled_workflow_after_include_expansion_and_argument_binding"
    },
    "inputs_contract": {
      "access_surface": "inputs.name",
      "declaration_fields": [
        {
          "authoring_role": "input_requiredness",
          "default_when_omitted": true,
          "name": "required",
          "required": false,
          "type": "boolean"
        },
        {
          "authoring_role": "input_default_value",
          "name": "default",
          "required": false,
          "runtime_effect": "applies_when_input_is_missing",
          "type": "json"
        },
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
      "declared_keys_required_at_activation": false,
      "default_semantics": {
        "default_makes_input_optional": true,
        "legacy_empty_object_shorthand_required": true,
        "legacy_scalar_shorthand_supported": true
      },
      "empty_string_is_distinct_value": true,
      "null_is_distinct_from_missing": true,
      "rejects_unknown_activation_inputs": true,
      "requiredness_surface": "per_input_required_field",
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
          "list_semantics": "implicit_all",
          "name": "if",
          "required": false,
          "structured_operators": [
            "all",
            "any",
            "not"
          ],
          "surface": "expression_or_structured_condition",
          "type": "condition"
        },
        {
          "authoring_role": "caller_scoped_step_admission_condition",
          "list_semantics": "implicit_all",
          "name": "gate",
          "required": false,
          "structured_operators": [
            "all",
            "any",
            "not"
          ],
          "structured_optional_fields": [
            {
              "authoring_role": "gate_failure_diagnostic_context",
              "evaluation_timing": "only_when_gate_verdict_is_failed",
              "name": "on_fail",
              "type": "object",
              "value_surface": "step_local_read_only_expression_or_literal"
            }
          ],
          "surface": "expression_or_structured_condition",
          "type": "condition"
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
        "step",
        "probe"
      ],
      "caller_scoped_condition_surface": [
        "inputs",
        "state",
        "step",
        "probe"
      ],
      "directive_field": "run",
      "execution_semantics": "runtime_scoped_fragment_invocation",
      "fan_out_surface": {
        "caller_step_scope": "not_directly_visible_inside_named_run_target_body",
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
          "item",
          "probe"
        ],
        "item_binding": "item",
        "outer_if_scope": "whole_invocation_step",
        "outer_register_scope": "aggregate_results"
      },
      "fragment_argument_access_surface": "args.name",
      "named_target_callee_scope": {
        "caller_data_transfer": "explicit_run_with_bindings_only",
        "caller_step_scope": "not_directly_visible_inside_callee_body",
        "direct_roots": [
          "inputs",
          "state",
          "args",
          "step",
          "probe"
        ],
        "let_scope": "callee_local_only",
        "step_scope": "callee_local_only"
      },
      "named_target_scope_boundary": "isolated_callee_scope",
      "surface_kind": "step_form"
    },
    "step_form_rules": [
      {
        "exception": "a standalone gate-only checkpoint step may omit a body form",
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
      },
      {
        "fields": [
          "gate",
          "register"
        ],
        "kind": "conflict",
        "message": "A workflow step must not define both gate and register. Split this into a standalone gate checkpoint step followed by a separate step that declares register.",
        "name": "gate_forbids_register"
      }
    ],
    "step_forms": [
      {
        "deprecated_optional_fields": [
          "launcher"
        ],
        "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
        "if_list_semantics": "implicit_all",
        "if_structured_operators": [
          "all",
          "any",
          "not"
        ],
        "name": "operation_call",
        "optional_fields": [
          "if",
          "gate",
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
        ],
        "with_value_surface": "bare_first_quoted_string_literals_embedded_escape_hatch"
      },
      {
        "for_each_value_surface": "bare_first_quoted_string_literals_embedded_escape_hatch",
        "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
        "if_list_semantics": "implicit_all",
        "if_structured_operators": [
          "all",
          "any",
          "not"
        ],
        "name": "run_invocation",
        "optional_fields": [
          "if",
          "gate",
          "with",
          "for_each",
          "register"
        ],
        "required_fields": [
          "name",
          "run"
        ],
        "with_value_surface": "bare_first_quoted_string_literals_embedded_escape_hatch"
      },
      {
        "for_each_value_surface": "bare_first_quoted_string_literals_embedded_escape_hatch",
        "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
        "if_list_semantics": "implicit_all",
        "if_structured_operators": [
          "all",
          "any",
          "not"
        ],
        "name": "inline_fan_out_invocation",
        "optional_fields": [
          "if",
          "gate",
          "register"
        ],
        "required_fields": [
          "name",
          "for_each",
          "steps"
        ]
      },
      {
        "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
        "if_list_semantics": "implicit_all",
        "if_structured_operators": [
          "all",
          "any",
          "not"
        ],
        "name": "profile_switch",
        "optional_fields": [
          "if",
          "gate"
        ],
        "required_fields": [
          "name",
          "profile_switch"
        ]
      },
      {
        "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
        "if_list_semantics": "implicit_all",
        "if_structured_operators": [
          "all",
          "any",
          "not"
        ],
        "name": "value",
        "optional_fields": [
          "if",
          "gate",
          "register"
        ],
        "required_fields": [
          "name",
          "value"
        ],
        "value_expression_surface": "bare_first_quoted_string_literals_embedded_escape_hatch"
      },
      {
        "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
        "if_list_semantics": "implicit_all",
        "if_structured_operators": [
          "all",
          "any",
          "not"
        ],
        "name": "result",
        "optional_fields": [
          "if",
          "gate"
        ],
        "required_fields": [
          "name",
          "result"
        ],
        "value_expression_surface": "bare_first_quoted_string_literals_embedded_escape_hatch"
      },
      {
        "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
        "if_list_semantics": "implicit_all",
        "if_structured_operators": [
          "all",
          "any",
          "not"
        ],
        "name": "publish",
        "optional_fields": [
          "if",
          "gate"
        ],
        "required_fields": [
          "name",
          "publish"
        ],
        "value_expression_surface": "bare_first_quoted_string_literals_embedded_escape_hatch"
      },
      {
        "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
        "if_list_semantics": "implicit_all",
        "if_structured_operators": [
          "all",
          "any",
          "not"
        ],
        "name": "state_set",
        "optional_fields": [
          "if",
          "gate"
        ],
        "required_fields": [
          "name",
          "state_set"
        ]
      },
      {
        "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
        "if_list_semantics": "implicit_all",
        "if_structured_operators": [
          "all",
          "any",
          "not"
        ],
        "name": "state_delete",
        "optional_fields": [
          "if",
          "gate"
        ],
        "required_fields": [
          "name",
          "state_delete"
        ]
      },
      {
        "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
        "if_list_semantics": "implicit_all",
        "if_structured_operators": [
          "all",
          "any",
          "not"
        ],
        "name": "gate_checkpoint",
        "optional_fields": [
          "if"
        ],
        "required_fields": [
          "name",
          "gate"
        ]
      }
    ],
    "surface_constraints": {
      "authored_surfaces": {
        "condition_field_forms": {
          "expression_embedded_string": "deprecated_compatibility",
          "expression_string": "native_local_expression",
          "gate_structured_optional_fields": [
            "on_fail"
          ],
          "structured_list": "implicit_all",
          "structured_object_operators": [
            "all",
            "any",
            "not"
          ]
        },
        "expression_first_value_fields": [
          "with",
          "value",
          "publish",
          "result",
          "for_each"
        ],
        "expression_first_value_rules": {
          "embedded_escape_form": "${...}",
          "nested_objects_and_lists": "recursive_leaf_rule",
          "plain_scalar_string": "local_expression",
          "quoted_string": "literal_string",
          "yaml_number_boolean_null": "native_literal"
        },
        "literal_only_fields": [
          "version",
          "workflow",
          "name",
          "uses",
          "run",
          "register",
          "launcher",
          "state_delete"
        ],
        "literal_only_keyed_fields": [
          "state_set"
        ],
        "native_condition_fields": [
          "let",
          "guards",
          "if",
          "gate"
        ]
      },
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
          "lookup",
          "only",
          "flatten",
          "first",
          "last",
          "length",
          "unique",
          "catch",
          "not_found"
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
          "lookup",
          "only",
          "flatten",
          "first",
          "last",
          "length",
          "unique",
          "catch",
          "not_found"
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
        "activation_timing": "before_guard_evaluation",
        "applicability": "internal_project_bound_workflows_only",
        "authoring_role": "workflow_owned_execution_profile_binding",
        "name": "profile",
        "required": false,
        "type": "string"
      },
      {
        "activation_requirement": "per_input_required_or_default_semantics",
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
