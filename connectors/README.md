# Connectors

Built-in public connector families live here.

This directory is the source-of-truth connector library layer.
`ordo.runtime` consumes it, and `ordo.connectors` may expose adapter or registry surfaces for runtime integration, but the family implementations themselves live here rather than in the runtime core.

A connector owns:
- shared bootstrap/runtime prerequisites
- family-level context
- one or more public operations

Fixed v0 connector domains:
- `gh`
- `git`
- `shell`

Possible future connector domains:
- `run`
- `ansible`
- `fs`
- `obsidian`
