# Operation catalog

This page lists public operations by connector namespace.

Use this page when you need to find a concrete operation that a workflow can call.

## runtime

Runtime compatibility and execution-context operations.

### Requirements

- None

### Available context

- None

### Operations

- [runtime.profile.use](../operations/runtime/profile-use.md) — Switch the runtime execution profile for later work in the current run.

## git

Operations for reading and changing local Git state.

### Requirements

- git binary available
- inside git repository

### Available context

- `repository_root`

### Operations

- [git.branch](../operations/git/branch.md) — Read the current Git branch.
- [git.branch.create](../operations/git/branch-create.md) — Create a new local Git branch.
- [git.branch.delete](../operations/git/branch-delete.md) — Delete a local Git branch.
- [git.branch.switch](../operations/git/branch-switch.md) — Switch the current checkout to a local Git branch.
- [git.branches](../operations/git/branches.md) — List local Git branches.
- [git.commit.amend](../operations/git/commit-amend.md) — Amend the current Git commit.
- [git.commit.create](../operations/git/commit-create.md) — Create a new Git commit from the current index.
- [git.commit.revert](../operations/git/commit-revert.md) — Create a Git commit that reverts another commit.
- [git.commits](../operations/git/commits.md) — Read a bounded list of Git commits.
- [git.index.add_all](../operations/git/index-add-all.md) — Stage all current worktree changes.
- [git.integrate.cherry_pick](../operations/git/integrate-cherry-pick.md) — Cherry-pick a Git commit onto the current checkout.
- [git.integrate.merge](../operations/git/integrate-merge.md) — Merge a Git ref into the current checkout.
- [git.integrate.merge_ff_only](../operations/git/integrate-merge-ff-only.md) — Fast-forward merge a Git ref into the current checkout.
- [git.integrate.rebase_onto](../operations/git/integrate-rebase-onto.md) — Rebase a Git branch range onto a new base.
- [git.range](../operations/git/range.md) — Compare two Git refs and report ahead/behind counts.
- [git.ref](../operations/git/ref.md) — Read metadata for a Git ref.
- [git.repo](../operations/git/repo.md) — Read Git repository metadata.
- [git.stash](../operations/git/stash.md) — List Git stash entries.
- [git.state](../operations/git/state.md) — Read the current Git working-state summary.
- [git.sync.fetch](../operations/git/sync-fetch.md) — Fetch Git refs from a remote.
- [git.sync.push](../operations/git/sync-push.md) — Push a local Git branch to a remote.
- [git.tag](../operations/git/tag.md) — Read tag.
- [git.tags](../operations/git/tags.md) — Inspect tags.
- [git.upstream](../operations/git/upstream.md) — Read upstream tracking information for the current branch.
- [git.worktree](../operations/git/worktree.md) — Read the current Git worktree state.
- [git.worktrees](../operations/git/worktrees.md) — List Git worktrees.

## gh

Operations for reading and changing GitHub state.

### Requirements

- gh binary available
- GitHub auth available

### Available context

- `host`
- `viewer`
- `scopes`

### Operations

- [gh.issue](../operations/gh/issue.md) — Read a GitHub issue.
- [gh.issue.body.append](../operations/gh/issue-body-append.md) — Append text to a GitHub issue body.
- [gh.issue.body.replace](../operations/gh/issue-body-replace.md) — Replace a GitHub issue body.
- [gh.issue.close](../operations/gh/issue-close.md) — Close a GitHub issue.
- [gh.issue.comment.add](../operations/gh/issue-comment-add.md) — Add a comment to a GitHub issue.
- [gh.issue.comments](../operations/gh/issue-comments.md) — Read comments from a GitHub issue.
- [gh.issue.create](../operations/gh/issue-create.md) — Create a GitHub issue.
- [gh.pr](../operations/gh/pr.md) — Read pull request metadata from GitHub.
- [gh.pr.checks](../operations/gh/pr-checks.md) — Read normalized status and check-run results from a GitHub pull request head.
- [gh.pr.comments](../operations/gh/pr-comments.md) — Read regular conversation comments from a GitHub pull request.
- [gh.pr.review_comments](../operations/gh/pr-review-comments.md) — Read line-level review comments from a GitHub pull request.
- [gh.pr.reviews](../operations/gh/pr-reviews.md) — Read submitted reviews from a GitHub pull request.
- [gh.pr.timeline](../operations/gh/pr-timeline.md) — Read normalized lifecycle events from a GitHub pull request timeline.
- [gh.project](../operations/gh/project.md) — Read a GitHub Project.
- [gh.project.field](../operations/gh/project-field.md) — Read metadata for a GitHub Project field.
- [gh.project.field.option](../operations/gh/project-field-option.md) — Check whether a GitHub Project field exposes a named option.
- [gh.project.issue](../operations/gh/project-issue.md) — Read one issue's membership and field values in a GitHub Project.
- [gh.project.issue.add](../operations/gh/project-issue-add.md) — Add a GitHub issue to a GitHub Project.
- [gh.project.issue.field_iteration.set](../operations/gh/project-issue-field-iteration-set.md) — Set an iteration field for a GitHub Project issue.
- [gh.project.issue.field_number.set](../operations/gh/project-issue-field-number-set.md) — Set a number field for a GitHub Project issue.
- [gh.project.issue.field_single_select.set](../operations/gh/project-issue-field-single-select-set.md) — Set a single-select field for a GitHub Project issue.
- [gh.project.items](../operations/gh/project-items.md) — Read normalized items from a GitHub Project.
- [gh.project.items.details](../operations/gh/project-items-details.md) — Return normalized GitHub Project items with stable content details

## shell

Low-level shell execution surface.

### Requirements

- supported shell available

### Available context

- `shell`
- `working_directory`

### Operations

- [shell.command](../operations/shell/command.md) — Run a shell command.

## fs

Operations in the `fs` namespace.

### Requirements

- None

### Available context

- None

### Operations

- [fs.file](../operations/fs/file.md) — Observe one filesystem path as one file snapshot with canonical content and file metadata.

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
  ]
}
```
