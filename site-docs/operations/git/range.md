# Git range

A workflow needs to compare two endpoints such as main and HEAD before deciding whether a branch is ahead, behind, or diverged.

Compare two Git revision endpoints and return their resolved object ids, merge base, and ahead/behind counts.

## Use when

- Later logic needs one merge-base-aware relationship summary instead of a readable commit list or one exact ref lookup.

## Do not use for

- Checking only whether one exact ref resolves; use connector.git.ref for the simpler single-ref lookup.
- Reading commit subjects or bodies across a revision slice; use connector.git.commits when the workflow needs readable history rather than ahead/behind math.

## What to provide

- `base`: required; provide one revision endpoint. `head`: required; provide the other revision endpoint, such as main and HEAD.

## Result and boundary

- Returns base, head, base_oid, head_oid, merge_base_oid when one exists, ahead_count, behind_count, and repository_root. Unresolvable endpoints have no comparison result; counts can become stale when history changes.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.git.ref`](ref.md): Resolve one exact ref instead of comparing two revision endpoints
- [`connector.git.commits`](commits.md): Read a commit-history slice after the workflow chooses a revision scope
- [`connector.git.branch`](branch.md): Read current checkout branch context before choosing base and head endpoints
- [`connector.git.upstream`](upstream.md): Read upstream-tracking context when the workflow first needs to choose a comparison target

## Exact machine contract

Use `ordo-help operation git.range --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### git_range_probe_step

Compare two Git revision endpoints when the workflow needs merge-base and ahead/behind facts rather than one exact ref lookup.

```yaml
      - name: inspect-range
        uses: git.range
        with:
          base: inputs.base_ref
          head: inputs.head_ref
```
### git_ref_range_flow

Inspect one exact ref and one endpoint comparison together so a workflow can separate single-ref validation from ahead/behind relationship facts.

```yaml
version: 0
workflow: inspect-git-ref-range
inputs:
  ref_name: {}
  base_ref: {}
  head_ref: {}
blocks:
  - guards: []
  - steps:
      - name: inspect-ref
        uses: git.ref
        with:
          ref: inputs.ref_name
        register: ref_info
      - name: inspect-range
        uses: git.range
        with:
          base: inputs.base_ref
          head: inputs.head_ref
        register: range_info
      - name: publish-summary
        publish:
          ref_exists: step.ref_info.outputs.exists
          ahead_count: step.range_info.outputs.ahead_count
          behind_count: step.range_info.outputs.behind_count
          summary: "Git ref and range workflow prepared"
```
