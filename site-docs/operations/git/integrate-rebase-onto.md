# Git integrate rebase-onto

A workflow needs to move a topic branch onto a new base while preserving only the branch-local commit range after one upstream split point.

Rewrite one non-default Git branch by replaying the commits after one upstream boundary onto a new base with rebase --onto semantics.

## Use when

- Use this for branch-range rewriting, not whole-ref integration into the current checkout and not a one-commit transplant.

## Result and boundary

- On success, the branch points to its newly rebased head revision.
- If replay produces conflicts or Git cannot begin or finish the rebase, the rewrite is blocked rather than reported as complete.
- Checks out (switches to) `branch` before replaying it, then returns branch, onto, and head_commit after replay as the newly rebased head revision. Missing references, protected default branch, conflicts, or blocks do not report a completed rewrite; resolve conflicts before later history actions.

## What to provide

- `branch`: required; provide the branch to rewrite. `upstream`: required; provide the upstream boundary. `onto`: required; provide the new base.

## Do not use for

- Integrating a target ref into the current checkout without rewriting branch history; use connector.git.integrate.merge or connector.git.integrate.merge_ff_only for those integration semantics.
- Rebasing the repository default branch or copying only one selected commit; this operation protects the default branch and is broader than connector.git.integrate.cherry_pick.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.git.integrate.merge`](integrate-merge.md): Sibling action for integrating by merge instead of rewriting one branch range onto a new base
- [`connector.git.integrate.cherry_pick`](integrate-cherry-pick.md): Sibling action for replaying one chosen commit instead of rebasing an entire branch-local range
- [`connector.git.range`](range.md): Compare base/head relationships before choosing onto and upstream boundaries
- [`connector.git.branch`](branch.md): Read current checkout branch identity when the workflow first needs to confirm which branch is being rewritten

## Exact machine contract

Use `ordo-help operation git.integrate.rebase_onto --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### git_integrate_rebase_onto_step

Rewrite one topic branch onto a new base when the workflow intentionally wants branch-range replay rather than merge-based integration.

```yaml
      - name: Rebase branch onto new base
        if: inputs.strategy == "rebase"
        uses: git.integrate.rebase_onto
        with:
          onto: inputs.onto_ref
          upstream: inputs.upstream_ref
          branch: inputs.branch_name
```
