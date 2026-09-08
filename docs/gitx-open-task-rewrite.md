# Native Task Activation Example

[`examples/set-active-task-from-gitx.yaml`](../examples/set-active-task-from-gitx.yaml)
is the source of truth for this illustrative rewrite of one `gitx.sh` task-opening
sequence. It uses native GitHub and Git operations, local expressions, gates, and
state writes. It is not a complete migration of `gitx.sh` and is not equivalent to
the canonical `.ordo` task workflow. The full YAML is linked rather than duplicated
here so comments and operation ordering remain reviewable in one place.

## Input and State Contracts

- `repository` and `project_id` are required inputs without real repository or project defaults. Supply your own authorized repository and project.
- `allowed_issue_types` is a list, default `[Task, Bug]`, not the old CSV contract.
- `allow_backlog` defaults to `false` and must be boolean.
- `remote` defaults to `origin` and names a configured remote; `base_branch` defaults to `main`. Its remote-tracking ref must exist after fetch.
- `issue_number`, `task_key`, `issue_title`, `issue_type`, and `repository_kind` contain illustrative defaults. Supply the intended task values. Branch naming uses lowercased input issue type, issue number, and trimmed/slugged input title; project type governs policy, not branch naming or remembered issue data.
- `state_needs.task_memory` requires a playbook state binding. The example declares the role, not a storage file.
- Profile fixtures contain demonstration project IDs only; they do not promise an operational repository/project setup.

## Native Sequence

1. Guard admission on boolean backlog permission, exactly one worktree, a clean working tree, and an open GitHub issue.
2. Add the issue to the project, then observe project membership and fields. The policy snapshot is deliberately taken after addition.
3. Require membership and a string project type in `allowed_issue_types`. Missing type blocks. Reject `Done` and `In review`; allow `Backlog` only with permission. Missing status is allowed by these gates.
4. Set project `Status` to `In progress` before starting Git work.
5. Compute the task branch from inputs and probe the local base. Fetch the configured remote's refs once, without a branch-specific fetch or pull, then require `refs/remotes/<remote>/<base_branch>` to exist.
6. If the local base exists, switch to it and fast-forward it from the remote-tracking base. A failed switch stops the sequence; it does not merge into whichever branch happened to be checked out.
7. Observe target-branch existence once and retain that snapshot. Switch to an existing target, or create it from the local base when available, otherwise from the remote-tracking base. Creation and switching are separate operations.
8. After successful branch selection, write issue number, input issue type/title, computed branch, and repository kind beneath `state.task_memory[inputs.task_key]`. These are separate writes, not a transaction. This example does not read back or delete them.
9. Run the optional trusted hook last.

## Trusted Hook Boundary

`post_open_command` defaults to an empty string and is skipped when empty. A
nonempty value is intentional executable code passed directly to `shell.command`.
It is the only remaining shell step, not a legacy shell fallback for project
policy or Git operations. Never interpolate ordinary issue titles, types, task
keys, or other untrusted data into this hook. Native operation arguments and
local-expression values elsewhere remain data.

This retained migration hook is not a recommendation to add `shell.command` to
new workflows. The published workflow-rules prohibition still applies; prefer
native operations for new authoring work.

## Failure and Partial Effects

Execution stops on a failing gate or operation, but previous effects are not
rolled back. Membership can remain even if subsequent policy fails. Project
status is already changed when later Git operations begin, so a fetch, ref gate,
base switch, merge, branch creation, or target switch failure can leave GitHub
effects behind. Fetch and base fast-forward effects can also remain. Successful
branch creation followed by a failed switch can leave the new local branch.

State writes begin only after branch selection, but an error in a later write can
leave earlier writes intact. Hook failure happens after state writes and does not
undo project, Git, or state effects. Review the failed step and observed state
before retrying; this example makes no atomicity or automatic rollback promise.

## Discovery and Verification

Inspect `ordo-help describe examples.set-active-task-from-gitx` (or add `--json`)
for the full canonical source excerpt and its verification metadata. The existing
`workflow_fragment` snippet runner accepts this example and `examples.let-bindings`
as full workflow documents. It validates their authored shape, including required
inputs and state needs, without invoking Git, GitHub, state persistence, or the
hook. `runner_verified` does not claim a live task activation succeeded.

The smaller `examples.let-bindings` example names reusable expressions, gates on
`enabled`, and publishes a branch label as data. It neither creates a Git branch
nor runs a shell command. Its focused execution tests separately cover defaults,
disabled admission, and hostile input values remaining data.
