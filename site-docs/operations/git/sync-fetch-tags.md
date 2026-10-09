# Git sync fetch tags

Refresh local tag refs from one configured remote without updating branches or merging work.

Fetch only remote tag refs from a configured remote.

## Use when

- A later decision needs remote tags, but remote-tracking branches must remain unchanged.
- Use a configured remote name, not an ad-hoc URL or path.

## Result and boundary

- `remote` identifies the source and `fetched=true` confirms tag-only fetch completed. The result does not claim that a new tag existed.
- The action neither updates branches nor merges work. It does not force-move conflicting local tags or prune locally retained tags.
- Returns `remote` and `fetched=true` after Git completes a tag-only fetch. A missing remote or tag conflict leaves tag state without confirmed refresh.

## What to provide

- `remote`: required; provide a configured remote name such as origin.

## Do not use for

- Refreshing remote-tracking branches; use connector.git.sync.fetch.
- Deleting local tags absent from the remote, forcing a changed tag, or publishing tags.

## Related references

Use these related references when the workflow needs tag facts or broader remote refresh.


- [`connector.git.tags`](tags.md): List local tags after a tag-only fetch.
- [`connector.git.sync.fetch`](sync-fetch.md): Refresh the ordinary remote-tracking refs.

## Exact machine contract

Use `ordo-help operation git.sync.fetch-tags --json` when you need the exact machine-readable input and result contract for this operation.
