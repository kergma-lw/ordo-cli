# Ordo help reference

Generated reference pages from `./ordo-help --json`.

This site is meant to be browsed as product reference rather than as a narrative tutorial.

## Start here

- [Workflow-authoring feature map](topics/features.md) — Inspect workflow features, named surfaces, and when to use them
- [Overview](topics/overview.md) — Start with a map of the main Ordo surfaces.
- [Workflow model](topics/model.md) — Browse the main workflow contracts.
- [Workflow rules](topics/workflow-rules.md) — Browse workflow rules, from the default check/review loop to fallback cautions.
- [Capabilities](topics/capabilities.md) — See which surfaces are supported, restricted, or deprecated.
- [Command-line reference](topics/command-line.md) — See the public CLI surface and how check, review, plan, and run differ.
- [Operation catalog](topics/operations.md) — Browse the public connector operations.
- [Examples](topics/examples.md) — Browse verified workflow examples from the repository.

## Navigation commands

These are interactive discovery surfaces in `ordo-help`, so they are listed here as commands rather than static pages.

- `snippet-coverage` — Inspect which public handles do and do not publish canonical verified snippets
- `operation` — Inspect one public operation by reference
- `describe` — Resolve a supported public topic
- `search` — Search topics, contract facts, and operation references

## Recommended first calls

- `ordo-help features` — Scan workflow features, named surfaces, and when to use them
- `ordo-help overview` — Get the Ordo world map
- `ordo-help model` — Learn the main DSL surfaces
- `ordo-help workflow-rules` — Learn preferred workflow rules, including paired check/review passes
- `ordo-help capabilities` — Learn capability boundaries
- `ordo-help command-line` — Inspect public launch commands, flags, and distinct check/review roles
- `ordo-help operations` — Inspect the public operation catalog
- `ordo-help examples` — Inspect verified repository examples
- `ordo-help snippet-coverage` — Inspect which public handles do and do not publish canonical verified snippets

## Operation reference

- [All operations](operations/index.md) — 69 published operations

## Full JSON reference

```json
{
  "examples": [
    "ordo-help features",
    "ordo-help overview",
    "ordo-help model",
    "ordo-help workflow-rules",
    "ordo-help capabilities",
    "ordo-help command-line",
    "ordo-help operations",
    "ordo-help examples"
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
      "command": "ordo-help features",
      "purpose": "Scan workflow features, named surfaces, and when to use them"
    },
    {
      "command": "ordo-help overview",
      "purpose": "Get the Ordo world map"
    },
    {
      "command": "ordo-help model",
      "purpose": "Learn the main DSL surfaces"
    },
    {
      "command": "ordo-help workflow-rules",
      "purpose": "Learn preferred workflow rules, including paired check/review passes"
    },
    {
      "command": "ordo-help capabilities",
      "purpose": "Learn capability boundaries"
    },
    {
      "command": "ordo-help command-line",
      "purpose": "Inspect public launch commands, flags, and distinct check/review roles"
    },
    {
      "command": "ordo-help operations",
      "purpose": "Inspect the public operation catalog"
    },
    {
      "command": "ordo-help examples",
      "purpose": "Inspect verified repository examples"
    },
    {
      "command": "ordo-help snippet-coverage",
      "purpose": "Inspect which public handles do and do not publish canonical verified snippets"
    }
  ],
  "tool_name": "ordo-help",
  "topics": [
    {
      "name": "features",
      "summary": "Inspect workflow features, named surfaces, and when to use them"
    },
    {
      "name": "overview",
      "summary": "Start with the Ordo world map"
    },
    {
      "name": "model",
      "summary": "Inspect the main workflow contracts"
    },
    {
      "name": "workflow-rules",
      "summary": "Inspect preferred workflow rules, paired check/review passes, routine cautions, early guards, and let usage"
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
      "name": "snippet-coverage",
      "summary": "Inspect which public handles do and do not publish canonical verified snippets"
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
