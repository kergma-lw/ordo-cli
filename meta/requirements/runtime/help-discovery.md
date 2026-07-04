# Runtime requirements for help discovery

## Role

- `ordo-help` must provide the project's stable public discovery CLI for zero-knowledge users and agents.
- `ordo-help` must consume runtime-owned introspection data and canonical contract metadata rather than inventing a second manually maintained knowledge base.

## Discovery path

- The root `ordo-help` command must act as a bootstrap surface rather than a generic usage dump.
- The public discovery path must escalate predictably from root discovery to focused topic discovery.
- A zero-knowledge caller must be able to discover what to query next without already knowing internal section names.

## Public topic vocabulary

- The initial public top-level vocabulary must include `overview`, `capabilities`, `model`, `operations`, and `examples`.
- The initial focused lookup vocabulary must include `operation <reference>`.
- The public vocabulary may expose `describe <topic>` and `search <query>` as discovery aids, but those surfaces must resolve back to the same stable topic model.
- Internal implementation names such as `workflow_contract` or `pattern_hints` must not be the primary public vocabulary for bootstrap.

## Output modes

- `ordo-help` must support both text output and machine-readable JSON output.
- `ordo-help --json` must return a stable root discovery response.
- Topic commands with `--json` must return stable machine-readable payloads suitable for deterministic agent follow-up.
- Text output may optimize readability, but JSON output must remain the reviewable contract surface.

## Launcher and locality

- `ordo-help` must be available through a project-local launcher in the repository root.
- The project-local launcher must locate and use the project virtual environment automatically.
- Ordinary use of `ordo-help` must not require manual activation of `.venv`.

## Bootstrap expectations

- The root discovery surface must explain what `ordo-help` is, what it can describe, how to ask for it, and what to query first.
- The root discovery surface must recommend an initial bootstrap sequence for zero-knowledge callers.
- That bootstrap sequence must start from the public topic vocabulary rather than from Python function names.
