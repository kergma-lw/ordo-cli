# Roadmap

## Stage 0 — skeleton

- repo scaffold
- initial schema
- examples
- meta docs

## Stage 1 — contract core

- stabilise minimal workflow schema
- define connector/operation contract shape
- define result/error envelope
- add validator
- make workflow and profile authoring agent-checkable from schema, examples, and structured diagnostics

## Stage 2 — first real connector operations

- `shell.command`
- `git.worktree`
- `git.branch`
- `gh.issue`
- `gh.project.item.fields`

## Stage 3 — explainable runtime

- `check`
- `plan`
- `execute`
- `explain`
- operation discoverability sufficient for composition-first authoring

## Stage 4 — local adaptation model

- local namespaces
- explicit override diagnostics

## Anti-goals for early stages

- no giant standard library;
- no expression language explosion;
- no distributed execution concerns;
- no silent compatibility hacks.
- no requirement that routine customization start with inventing new connectors.
