# Git ref

A workflow needs one exact ref existence check such as HEAD, refs/heads/main, or origin/main before making a narrower branch, tag, or sync decision.

Check one named Git ref and report whether it resolves, which object id it names, and whether it is a symbolic ref with a separate target.

## Use when

- Later logic needs one ref's oid or symbolic-target facts without comparing two revisions or listing an inventory.

## Do not use for

- Comparing two revision endpoints for ahead/behind or merge-base facts; use connector.git.range for that relationship comparison.
- Reading tag-specific semantics or tag inventories; use connector.git.tag or connector.git.tags when the workflow is really about Git tags rather than generic refs.

## What to provide

- `ref`: required; provide the exact revision name to inspect, such as HEAD or refs/heads/main, without guessing a replacement when it is absent.

## Result and boundary

- Returns name, exists, oid, symbolic, symbolic_target, and repository_root. A missing ref succeeds with exists=false and unknown object facts; refs may change after this observation.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.git.range`](range.md): Compare two revision endpoints rather than resolve one exact ref
- [`connector.git.tag`](tag.md): Check one exact Git tag when tag semantics matter more than generic ref resolution
- [`connector.git.branch`](branch.md): Read current checkout branch context rather than one arbitrary named ref
- [`connector.git.tags`](tags.md): List tags instead of looking up one exact ref

## Exact machine contract

Use `ordo-help operation git.ref --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### git_ref_probe_step

Inspect one exact Git ref before branching on existence, symbolic-target behavior, or downstream comparison choices.

```yaml
      - name: inspect-ref
        uses: git.ref
        with:
          ref: inputs.ref_name
        register: ref_info
```
