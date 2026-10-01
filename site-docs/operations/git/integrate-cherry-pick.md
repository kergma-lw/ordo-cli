# Git integrate cherry-pick

A workflow needs one targeted commit transplant such as backporting one fix without merging or rebasing the larger branch that originally contained it.

Apply one existing non-merge Git commit onto the current checkout as a new commit, without integrating the whole source ref history.

## Use when

- Use this for one chosen commit identity, not to integrate a whole ref tip or replaying a branch range onto a new base.

## Result and boundary

- On success, the current checkout gains a new commit containing the selected commit's change, and reports the resulting head revision.
- Conflicts, unsupported merge commits, or other Git blocks do not produce a completed transplant result.
- Returns picked_commit, head_commit, and branch. A missing or merge commit, conflict, or other block does not produce a completed transplant; resolve conflicts before further integration.

## What to provide

- `commit`: required; provide the one non-merge commit to transplant.

## Do not use for

- Integrating a whole branch tip or preserving branch topology; use connector.git.integrate.merge or connector.git.integrate.merge_ff_only when the unit of integration is one ref rather than one commit.
- Cherry-picking merge commits or rewriting one topic branch onto a new base; this operation rejects merge commits and is narrower than connector.git.integrate.rebase_onto.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.git.integrate.merge`](integrate-merge.md): Sibling action for integrating a whole target ref instead of transplanting one selected commit
- [`connector.git.integrate.rebase_onto`](integrate-rebase-onto.md): Sibling action for replaying a branch range onto a new base rather than copying one chosen commit
- [`connector.git.commits`](commits.md): Read commit history before choosing which commit to cherry-pick
- [`connector.git.ref`](ref.md): Resolve an exact ref when the workflow still needs to identify the source commit or source branch first

## Exact machine contract

Use `ordo-help operation git.integrate.cherry_pick --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### git_integrate_cherry_pick_step

Cherry-pick one chosen commit when the workflow wants a targeted backport-style transplant instead of integrating the whole source ref.

```yaml
      - name: cherry-pick-target-commit
        if: inputs.strategy == "cherry-pick"
        uses: git.integrate.cherry_pick
        with:
          commit: inputs.target_commit
```
