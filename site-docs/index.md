# Ordo help reference

Generated reference pages from `./ordo-help --json`.

This site is meant to be browsed as product reference rather than as a narrative tutorial.

## Start here

- [Overview](topics/overview.md) — Start with a map of the main Ordo surfaces.
- [Authoring model](topics/model.md) — Browse the main authoring contracts.
- [Workflow authoring](topics/workflow-authoring.md) — Browse workflow authoring guidance, from the default check/review loop to fallback cautions.
- [Capabilities](topics/capabilities.md) — See which surfaces are supported, restricted, or deprecated.
- [Command-line reference](topics/command-line.md) — See the public CLI surface and how check, review, plan, and run differ.
- [Operation catalog](topics/operations.md) — Browse the public connector operations.
- [Examples](topics/examples.md) — Browse verified workflow examples from the repository.

## Navigation commands

These are interactive discovery surfaces in `ordo-help`, so they are listed here as commands rather than static pages.

- `operation` — Inspect one public operation by reference
- `describe` — Resolve a supported public topic
- `search` — Search topics, contract facts, and operation references

## Recommended first calls

- `ordo-help overview --json` — Get the Ordo world map
- `ordo-help model --json` — Learn the main DSL surfaces
- `ordo-help workflow-authoring --json` — Learn preferred workflow authoring patterns, including paired check/review passes
- `ordo-help capabilities --json` — Learn capability boundaries
- `ordo-help command-line --json` — Inspect public launch commands, flags, and distinct check/review roles
- `ordo-help operations --json` — Inspect the public operation catalog
- `ordo-help examples --json` — Inspect verified repository examples

## Operation reference

- [All operations](operations/index.md) — 42 published operations

## Full JSON reference

```json
{
  "examples": [
    "ordo-help overview --json",
    "ordo-help model --json",
    "ordo-help workflow-authoring --json",
    "ordo-help capabilities --json",
    "ordo-help command-line --json",
    "ordo-help operations --json",
    "ordo-help examples --json"
  ],
  "introspection": {
    "entrypoint": "describe_system",
    "published_sections": [
      "capabilities",
      "errors",
      "examples_catalog",
      "operations",
      "pattern_hints",
      "playbook_contract",
      "plugin_surface_contract",
      "profile_contract",
      "routine_contract",
      "state_contract",
      "workflow_contract"
    ],
    "version": 1
  },
  "output_modes": [
    "text",
    "json"
  ],
  "purpose": "Self-describing discovery CLI for Ordo",
  "recommended_first_calls": [
    {
      "command": "ordo-help overview --json",
      "purpose": "Get the Ordo world map"
    },
    {
      "command": "ordo-help model --json",
      "purpose": "Learn the main DSL surfaces"
    },
    {
      "command": "ordo-help workflow-authoring --json",
      "purpose": "Learn preferred workflow authoring patterns, including paired check/review passes"
    },
    {
      "command": "ordo-help capabilities --json",
      "purpose": "Learn capability boundaries"
    },
    {
      "command": "ordo-help command-line --json",
      "purpose": "Inspect public launch commands, flags, and distinct check/review roles"
    },
    {
      "command": "ordo-help operations --json",
      "purpose": "Inspect the public operation catalog"
    },
    {
      "command": "ordo-help examples --json",
      "purpose": "Inspect verified repository examples"
    }
  ],
  "tool_name": "ordo-help",
  "topics": [
    {
      "name": "overview",
      "summary": "Start with the Ordo world map"
    },
    {
      "name": "model",
      "summary": "Inspect the main authoring contracts"
    },
    {
      "name": "workflow-authoring",
      "summary": "Inspect preferred workflow authoring patterns, paired check/review passes, routine cautions, early guards, and let usage"
    },
    {
      "name": "capabilities",
      "summary": "Inspect supported and unsupported surfaces"
    },
    {
      "name": "command-line",
      "summary": "Inspect the public command-line launch surface, including distinct check and review roles"
    },
    {
      "name": "operations",
      "summary": "Inspect the public connector catalog"
    },
    {
      "name": "examples",
      "summary": "Inspect verified repository examples"
    },
    {
      "name": "operation",
      "summary": "Inspect one public operation by reference"
    },
    {
      "name": "describe",
      "summary": "Resolve a supported public topic"
    },
    {
      "name": "search",
      "summary": "Search topics, contract facts, and operation references"
    }
  ]
}
```
