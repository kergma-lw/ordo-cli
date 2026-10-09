# Git tag

A workflow needs to confirm one specific tag such as v1.2.3 before branching on release presence or publishing tag metadata.

Check one named Git tag and report whether it exists, which ref it occupies, and whether the stored object is an annotated tag object or a lightweight commit ref, including the peeled target identity.

## Use when

- Later logic needs the single-tag existence result plus the raw tag ref, stored object identity, and peeled target identity, not a broader tag inventory.

## Do not use for

- Listing or pattern-matching many tags; use connector.git.tags for the inventory.
- Inferring the newest tag by version ordering across many candidates; use connector.git.tags and its latest output for that collection-oriented question.

## What to provide

- `name`: required; provide the exact tag to inspect in the current repository.

## Result and boundary

- Returns name, ref, exists, oid, annotated, target_oid, target_type, and repository_root. A missing tag succeeds with exists=false and unknown object facts; an invalid name or unreadable repository has no partial result.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.git.tags`](tags.md): List tags instead of inspecting one named tag lookup
- [`connector.git.ref`](ref.md): Check refs when the workflow cares about refs broadly rather than Git tag semantics specifically
- [`connector.git.commits`](commits.md): Read commit history when one tag lookup alone is not enough context
- [`connector.git.range`](range.md): Compare a revision range when the question is broader than one named tag

## Exact machine contract

Use `ordo-help operation git.tag --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### git_tag_probe_step

Inspect one exact Git tag before branching on its existence or publishing its stored and peeled target identities.

```yaml
      - name: Inspect exact tag
        uses: git.tag
        with:
          name: inputs.tag_name
        register: exact_tag
```
