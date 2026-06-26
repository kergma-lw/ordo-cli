# Connector invariants

## Core invariants

- workflows reference only public connector operations
- fixed v0 connector domains are `git`, `gh`, and `shell`
- connector semantics are public and stable
- connector operation kinds fixed so far are `probe` and `action`
- connector operations preserve structured results on success, failure, and exception paths
- `probe` remains semantically read-only and `action` remains the effectful operation kind
- silent same-name shadowing is not default behavior

## Drift rule

If a change breaks any invariant, `meta/` must be updated explicitly in the same work.
