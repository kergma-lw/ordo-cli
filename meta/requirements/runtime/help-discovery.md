# Runtime requirements for help discovery

## Role

- `ordo-help` must provide the project's stable public discovery CLI for zero-knowledge users and agents.
- `ordo-help` must consume runtime-owned introspection data and canonical contract metadata rather than inventing a second manually maintained knowledge base.

## Discovery path

- The root `ordo-help` command must act as a bootstrap surface rather than a generic usage dump.
- The public discovery path must escalate predictably from root discovery to focused topic discovery.
- A zero-knowledge caller must be able to discover what to query next without already knowing internal section names.

## Public topics

- The initial public top-level topics must include `overview`, `capabilities`, `model`, `command-line`, `operations`, `examples`, and `snippet-coverage`.
- Internal implementation names such as `workflow_contract` or `pattern_hints` must not be the primary public topic surface for bootstrap.

## Canonical example visibility

- `ordo-help describe <topic>` must publish explicit canonical-snippet coverage state for describable handles, including the explicit absence state `none`.
- Where canonical short examples are published, they must be backed either by verified excerpts from repository examples or by declared harness-based validation of the minimal form.
- The public help surface must provide one machine-readable way to inspect which describable handles are covered and which are still uncovered.

## Discovery actions

- The initial focused lookup actions must include `operation <reference>`.
- The public discovery surface may expose `describe <topic>` and `search <query>` as discovery aids, but those actions must resolve back to the same stable topic model.
- Public topics are the stable map of the help surface; discovery actions are navigation aids over that map.

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
- That bootstrap sequence must start from the public topics rather than from Python function names.

## Workflow authoring guidance exposure

- `ordo-help` must explain that `ordo-playbook check <workflow>` and `ordo-playbook review <workflow>` serve different authoring purposes.
- `ordo-help` must not imply that `check` alone is sufficient workflow-authoring sign-off when a workflow was added or changed.
- The `overview`, `workflow-authoring`, and `command-line` topics must make the paired use of `check` and `review` explicit for workflow authoring work.
