# Git integrate merge

A workflow intentionally wants one merge commit that preserves the integration event instead of silently linearizing history.

Integrate one target Git ref into the current checkout by creating a merge commit with ordinary merge semantics, even when a fast-forward would have been possible.

## Use when

- The integration target is one ref such as feature/demo or origin/main, not one standalone commit transplant or one branch-range rewrite.

## Result and boundary

- On success, the current checkout contains the target ref and points to the resulting head revision.
- If Git finds conflicts or blocks the merge, the action does not report the target as integrated.
- Returns merged_ref, head_commit, and branch after creating the integration commit. A missing ref, conflict, or block does not report integration; choose merge_ff_only when an explicit merge commit is unacceptable.

## What to provide

- `ref`: required; provide the target revision to integrate. Confirm that creating an integration commit is the intended history policy before merging it into the current checkout.

## Do not use for

- Requiring a linear-history-only fast-forward update; use connector.git.integrate.merge_ff_only when creating a merge commit would be the wrong outcome.
- Replaying one commit or rewriting a topic branch onto a new base; use connector.git.integrate.cherry_pick or connector.git.integrate.rebase_onto for those narrower rewrite semantics.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.git.integrate.merge_ff_only`](integrate-merge-ff-only.md): Sibling action for integrating one target ref only when the current checkout can fast-forward without creating a merge commit
- [`connector.git.integrate.cherry_pick`](integrate-cherry-pick.md): Sibling action for copying one commit onto the current checkout without merging a whole target ref
- [`connector.git.integrate.rebase_onto`](integrate-rebase-onto.md): Sibling action for rewriting one branch range onto a new base instead of integrating into the current checkout by merge
- [`connector.git.range`](range.md): Compare ahead/behind or merge-base facts before choosing an integration strategy

## Exact machine contract

Use `ordo-help operation git.integrate.merge --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### git_integrate_merge_step

Merge one target ref into the current checkout when the workflow explicitly wants an integration commit instead of a fast-forward-only update.

```yaml
      - name: Merge target reference
        if: inputs.strategy == "merge"
        uses: git.integrate.merge
        with:
          ref: inputs.target_ref
```
### git_integration_strategy_flow

Contrast merge, fast-forward-only merge, cherry-pick, and rebase --onto in one teaching workflow so each Git integration surface keeps its own unit of change and history semantics.

```yaml
version: 0
workflow: choose-git-integration-strategy
inputs:
  strategy: {}
  target_ref: {}
  target_commit: {}
  onto_ref: {}
  upstream_ref: {}
  branch_name: {}
blocks:
   - guards: []
   - steps:
      # Apply the selected integration strategy.
      - name: Compare branch range
        uses: git.range
        with:
          base: inputs.upstream_ref
          head: inputs.branch_name
        register: branch_range
      - name: Merge target reference
        if: inputs.strategy == "merge"
        uses: git.integrate.merge
        with:
          ref: inputs.target_ref
      - name: Fast-forward target reference
        if: inputs.strategy == "fast-forward"
        uses: git.integrate.merge_ff_only
        with:
          ref: inputs.target_ref
      - name: Cherry-pick target commit
        if: inputs.strategy == "cherry-pick"
        uses: git.integrate.cherry_pick
        with:
          commit: inputs.target_commit
      - name: Rebase branch onto new base
        if: inputs.strategy == "rebase"
        uses: git.integrate.rebase_onto
        with:
          onto: inputs.onto_ref
          upstream: inputs.upstream_ref
          branch: inputs.branch_name
      - name: Publish summary
        publish:
          merge_base: step.branch_range.outputs.merge_base
          compared_head: step.branch_range.outputs.head_oid
          summary: "Choose exactly one reviewed path: merge for an integration commit, fast-forward only for a linear advance, cherry-pick for one commit, or rebase onto for a topic-branch rewrite."
```
