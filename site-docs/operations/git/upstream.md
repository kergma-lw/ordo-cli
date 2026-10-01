# Git upstream

A workflow needs to know whether the current branch has a tracked branch before comparing divergence or deciding whether publishing makes sense.

Observe the current branch tracking relationship, including whether one exists and the related remote and branch names.

## Use when

- A workflow needs to know whether the current branch tracks one upstream before comparing ahead/behind state or deciding whether pushing makes sense.
- Later logic needs the tracked branch relationship for the current branch rather than a repository-wide inventory.

## Do not use for

- Reading repository-root or default-branch facts; use connector.git.repo for repository-level context.
- Comparing current branch divergence against its upstream; use connector.git.range when the workflow needs ahead/behind math after choosing base and head endpoints.
- Determining destinations, access, or publication safety.

## What to provide

- No inputs are required; use the current checkout whose tracked branch relationship matters.

## Result and boundary

- Returns configured, branch, upstream_ref, remote, remote_branch, and repository_root. A detached checkout or branch without tracking is reported with configured=false; unavailable or inconsistent tracking information fails without a guessed result.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.git.repo`](repo.md): Read repository-level facts before or alongside upstream-tracking inspection
- [`connector.git.branch`](branch.md): Read current branch identity when the workflow first needs the branch name itself
- [`connector.git.range`](range.md): Compare ahead/behind and merge-base facts after an upstream target is known
- [`connector.git.sync.push`](sync-push.md): Push once upstream-tracking context has been confirmed

## Exact machine contract

Use `ordo-help operation git.upstream --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### git_upstream_probe_step

Inspect the current branch's tracked remote and branch names before deciding whether publication is appropriate.

```yaml
      - name: inspect-upstream
        uses: git.upstream
        register: upstream_info
```
### git_repo_upstream_flow

Publish repository context and the current branch's tracked remote and branch relationship for a later decision.

```yaml
version: 0
workflow: inspect-git-repo-upstream
blocks:
  - guards: []
  - steps:
      - name: inspect-repo
        uses: git.repo
        register: repo_info
      - name: inspect-upstream
        uses: git.upstream
        register: upstream_info
      - name: publish-summary
        publish:
          repo_root: step.repo_info.outputs.root
          upstream_configured: step.upstream_info.outputs.configured
          upstream_ref: step.upstream_info.outputs.upstream_ref
          remote: step.upstream_info.outputs.remote
          remote_branch: step.upstream_info.outputs.remote_branch
          summary: "Git repo and upstream workflow prepared"
```
