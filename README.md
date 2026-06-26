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
- `src/ordo/model/` — core workflow, profile, connector, diagnostic, and runtime models
- `src/ordo/runtime/` — runtime mode orchestration surface
- `src/ordo/connectors/` — Python connector package namespace

Notable docs:
- `docs/format.md` — current format draft
- `docs/pypyr-comparison.md` — honest positioning notes vs pypyr
- `docs/gitx-open-task-rewrite.md` — example rewrite of a gitx ritual slice
- `meta/notes/positioning-and-value.md` — longer internal notes on positioning and value

## Core ideas

- declarative workflows
- explicit guards
- explicit steps
- public connector families
- connector operations
- `check` / `plan` / `execute` / `explain`
- structured results

## Status

This repository currently contains only the minimal format skeleton:
- initial workflow schema
- initial format notes
- a couple of examples
