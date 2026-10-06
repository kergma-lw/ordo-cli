# Git integrate merge-ff-only

A workflow wants linear-history integration and should fail cleanly rather than synthesize a merge commit for the target ref.

Integrate one target Git ref into the current checkout only if the update can fast-forward, refusing to create a merge commit when histories have diverged.

## Use when

- Use this specifically to advance the current checkout to one descendant ref, not about copying one commit or rewriting a topic branch range.

## Result and boundary

- On success, the current checkout advances to the target ref without creating a merge commit.
- When the histories cannot fast-forward, or Git otherwise blocks the update, the action does not report an integration result.
- Returns merged_ref, head_commit, and branch only after the current checkout advances without a merge commit. A missing ref, non-fast-forward relationship, or block leaves no integration result; use merge when an explicit merge commit is intended.

## What to provide

- `ref`: required; provide the target revision to integrate. Use this only after confirming the current checkout can advance without creating an integration commit.

## Do not use for

- Preserving an explicit integration commit even when fast-forward would be possible; use connector.git.integrate.merge for ordinary merge semantics.
- Branch-range rewrites or single-commit transplants; use connector.git.integrate.rebase_onto or connector.git.integrate.cherry_pick for those rewrite-oriented operations.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.git.integrate.merge`](integrate-merge.md): Sibling action for integrating the same target ref through an explicit merge commit instead of fast-forward-only admission
- [`connector.git.range`](range.md): Compare two endpoints to confirm whether they are already in a fast-forward relationship before this action runs
- [`connector.git.upstream`](upstream.md): Read current-branch upstream context when the workflow first needs to choose which target ref should fast-forward
- [`connector.git.integrate.rebase_onto`](integrate-rebase-onto.md): Sibling action for rewriting branch history when linear movement requires replay rather than pure fast-forward integration

## Exact machine contract

Use `ordo-help operation git.integrate.merge_ff_only --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### git_integrate_merge_ff_only_step

Advance the current checkout to one target ref only when the histories already allow a fast-forward update.

```yaml
      - name: Fast-forward target reference
        if: inputs.strategy == "fast-forward"
        uses: git.integrate.merge_ff_only
        with:
          ref: inputs.target_ref
```
