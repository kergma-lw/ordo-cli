# Git tags

A workflow needs to inspect several tags at once, optionally narrowing them by release naming conventions such as v* or one semantic-version regex.

List Git tags as a version-sorted collection, optionally narrowed by glob or regex matching, and return matching tags plus the first match as latest in that sorted order.

## Use when

- Later logic needs both the full matching tag list and the first version-sorted match, not just one named tag existence check.

## Do not use for

- Checking only one specific tag by exact name; use connector.git.tag for that simpler single-tag lookup.
- Treating latest as newest by creation date; this operation orders by descending version refname, not by tag creation time.

## What to provide

- `match`: optional; provide it to narrow tags. `match_kind`: conditional; when `match` is supplied, provide `glob` or `regex`. Omit both to inspect all tags.

## Result and boundary

- Returns count, matching items, latest, and repository_root. latest is the first matching tag in descending version order, or null when no tag matches; it is not based on creation time. Invalid matching input or unreadable tags has no partial result.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.git.tag`](tag.md): Check one exact tag instead of listing the inventory
- [`connector.git.range`](range.md): Compare a revision range when tag inventory is broader than needed
- [`connector.git.commits`](commits.md): Read commit history after a tag inventory decision chooses a revision scope
- [`connector.git.ref`](ref.md): Check explicit refs when the workflow does not need tag-specific inventory semantics

## Exact machine contract

Use `ordo-help operation git.tags --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### git_tags_probe_step

Inspect a version-sorted Git tag inventory when the workflow needs more than one exact tag lookup.

```yaml
      - name: inspect-release-tags
        uses: git.tags
        with:
          match: "v*"
          match_kind: "glob"
        register: release_tags
```
### git_tag_inventory_flow

Inspect one exact tag and one matching tag inventory together so a workflow can compare single-tag existence with broader release-tag discovery.

```yaml
version: 0
workflow: inspect-git-tags
inputs:
  tag_name: {}
blocks:
  - guards: []
  - steps:
      - name: inspect-exact-tag
        uses: git.tag
        with:
          name: inputs.tag_name
        register: exact_tag
      - name: inspect-release-tags
        uses: git.tags
        with:
          match: "v*"
          match_kind: "glob"
        register: release_tags
      - name: publish-summary
        publish:
          tag_exists: step.exact_tag.outputs.exists
          release_tag_count: step.release_tags.outputs.count
          summary: "Git tag workflow prepared"
```
