# Overview

Start here for a map of the main Ordo surfaces.

Use this page first when you need to understand where to look next.

**CLI purpose:** World map for Ordo discovery and authoring bootstrap

## Published topics

- `overview`
- `model`
- `workflow-authoring`
- `capabilities`
- `command-line`
- `operations`
- `examples`
- `operation`
- `describe`
- `search`

## Connector namespaces

- `runtime` — Runtime compatibility and execution-context operations.
- `git` — Operations for reading and changing local Git state.
- `gh` — Operations for reading and changing GitHub state.
- `shell` — Low-level shell execution surface.
- `fs` — Operations in the `fs` namespace.

## Execution concepts

### Modes

- `review`
- `check`
- `plan`
- `execute`
- `explain`

### Statuses

- `ok`
- `guard_failed`
- `validation_error`
- `resolution_error`
- `execution_error`

## Workflow authoring loop

Use both check and review after adding or changing a workflow; neither replaces the other.

- `ordo-playbook check <workflow>` — Validate workflow applicability and execution readiness
- `ordo-playbook review <workflow>` — Review workflow authoring-quality findings

## Recommended next calls

- `ordo-help model --json` — Learn the main DSL surfaces
- `ordo-help workflow-authoring --json` — Learn preferred workflow authoring patterns, including paired check/review passes
- `ordo-help capabilities --json` — Learn capability boundaries
- `ordo-help command-line --json` — Inspect public launch commands, flags, and distinct check/review roles
- `ordo-help operations --json` — Inspect the public operation catalog
- `ordo-help examples --json` — Inspect verified repository examples

## Full JSON reference

```json
{
  "connector_namespaces": [
    "runtime",
    "git",
    "gh",
    "shell",
    "fs"
  ],
  "document_kind": "overview",
  "document_kinds": [
    "error_taxonomy",
    "examples_catalog",
    "pattern_hints",
    "playbook",
    "plugin_surface_contract",
    "profile",
    "routine_registry",
    "state_contract",
    "workflow"
  ],
  "execution_concepts": {
    "modes": [
      "review",
      "check",
      "plan",
      "execute",
      "explain"
    ],
    "statuses": [
      "ok",
      "guard_failed",
      "validation_error",
      "resolution_error",
      "execution_error"
    ]
  },
  "published_topics": [
    "overview",
    "model",
    "workflow-authoring",
    "capabilities",
    "command-line",
    "operations",
    "examples",
    "operation",
    "describe",
    "search"
  ],
  "purpose": "World map for Ordo discovery and authoring bootstrap",
  "recommended_next_calls": [
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
  "workflow_authoring_passes": {
    "passes": [
      {
        "command": "ordo-playbook check <workflow>",
        "purpose": "Validate workflow applicability and execution readiness"
      },
      {
        "command": "ordo-playbook review <workflow>",
        "purpose": "Review workflow authoring-quality findings"
      }
    ],
    "rule": "Use both check and review after adding or changing a workflow; neither replaces the other."
  }
}
```
