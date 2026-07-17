# Ordo

Local declarative workflow runtime built around public connector contracts.

## Goal

Ordo is a small runtime for describing local operational workflows in a readable way.

Target use cases:
- repo rituals
- agent helpers
- guarded local automation
- human + machine authored workflow files

## Design shape

- `connectors/` — public connector families and operations
- `schema/` — machine-readable format
- `docs/` — human-readable spec
- `examples/` — valid minimal examples
- `profiles/` — reusable presets, defaults, and explicit overrides
- `src/ordo/model/` — core workflow, profile, connector, diagnostic, and runtime models
- `src/ordo/runtime/` — runtime mode orchestration surface
- `src/ordo/connectors/` — Python connector package namespace

Notable docs:
- `docs/quickstart.md` — fastest path to loading, checking, planning, explaining, and executing examples
- `docs/ordo.1.md` — man-style overview of current capabilities and usage
- `docs/playbook.md` — initial project-local playbook contract and discovery rules
- `docs/format.md` — current format draft
- `docs/contracts.md` — stable v0 workflow and runtime result contracts
- `docs/pypyr-comparison.md` — honest positioning notes vs pypyr
- `docs/gitx-open-task-rewrite.md` — example rewrite of a gitx ritual slice
- `docs/architecture/positioning-and-value.md` — longer internal notes on positioning and value

## Core ideas

- declarative workflows
- explicit guards
- explicit steps
- public connector families
- connector operations
- `check` / `plan` / `execute` / `explain`
- structured results

## Status

This repository now contains the v0 contract-first runtime foundation:
- workflow and profile loading
- strict validation and structured diagnostics
- public connector registry and stable resolution
- runtime modes: `check`, `plan`, `execute`, `explain`
- initial canonical connector operations
- examples, profiles, and golden outputs

There is not yet a stable end-user CLI; the current surface is primarily a Python API.
