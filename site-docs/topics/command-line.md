# Command-line reference

This page summarizes the public CLI surface and the main execution modes.

Use this page when you need the public CLI entrypoints, flags, and execution modes.

## ordo-playbook

Browse playbook workflows, ask which workflow should run next, or launch one named workflow into one runtime mode

**Usage:** `ordo-playbook [--file PATH] [--profile NAME] [--input KEY=VALUE] [--input-file KEY=PATH] [--graph] [--json] <command>`

### Modes

- `review <workflow>` — review authoring-quality findings without making changes
- `check <workflow>` — check whether the workflow can be run now, without making changes
- `plan <workflow>` — show what the workflow would do, without making changes
- `explain <workflow>` — explain why the workflow can or cannot be run right now
- `run <workflow>` — run the workflow and do the real work
- `next` — suggest which workflow should run next from the current playbook context, preferring state-connected continuation over world-blocked or unrelated options

### Next priority

- prefer workflows tied to the active state-backed work context over unrelated utility workflows
- prefer workflows blocked only by execution-only operator input over workflows blocked by world-state mismatch
- keep inspection-only workflows below continuation-capable workflows when both are otherwise credible

### Flags

- `--file` (`PATH`) — Use one explicit playbook file path
- `--profile` (`NAME`) — Select one named profile for this run
- `--input` (`KEY=VALUE`) — Add or override one top-level workflow input from an inline YAML value
- `--input-file` (`KEY=PATH`) — Add or override one top-level workflow input from a raw UTF-8 file string
- `--graph` — With `next`, show the inferred state-topology graph behind the recommendation
- `--json` — Emit JSON without extra decoration

### Discovery commands

- `workflows list` — list declared playbook workflows with project-local descriptions
- `workflows show <workflow>` — show one workflow entry with file metadata and playbook invocation inputs; `--json` also includes declared workflow inputs

### Input override precedence

- workflow.inputs declares the allowed activation keys; declared keys are required at activation=true
- profile.inputs may supply values for declared workflow inputs
- --input overrides workflow and profile-provided values for one run
- --input-file overrides workflow and profile-provided values for one run
- unknown activation inputs are rejected=true
- when both --input and --input-file set the same key, --input-file wins

### Workflow authoring loop

When authoring or modifying workflows, run both check and review. Neither replaces the other.

- `check <workflow>` — Validate applicability, observations, and execution readiness _Question: Can this workflow run now?_
- `review <workflow>` — Surface workflow authoring-quality findings _Question: Is this workflow well-authored?_

### Example commands

- `ordo-playbook workflows list`
- `ordo-playbook workflows show inspect-issue`
- `ordo-playbook next`
- `ordo-playbook next --graph`
- `ordo-playbook plan inspect-issue`
- `ordo-playbook --profile review plan inspect-issue`
- `ordo-playbook --input enabled=true plan inspect-issue`
- `ordo-playbook --input-file body=./prompt.md plan inspect-issue`

## Full JSON reference

```json
{
  "commands": [
    {
      "authoring_passes": {
        "passes": [
          {
            "mode": "check <workflow>",
            "purpose": "Validate applicability, observations, and execution readiness",
            "question": "Can this workflow run now?"
          },
          {
            "mode": "review <workflow>",
            "purpose": "Surface workflow authoring-quality findings",
            "question": "Is this workflow well-authored?"
          }
        ],
        "rule": "When authoring or modifying workflows, run both check and review. Neither replaces the other."
      },
      "discovery_commands": [
        {
          "name": "workflows list",
          "summary": "list declared playbook workflows with project-local descriptions"
        },
        {
          "name": "workflows show <workflow>",
          "summary": "show one workflow entry with file metadata and playbook invocation inputs; --json also includes declared workflow inputs"
        }
      ],
      "examples": [
        "ordo-playbook workflows list",
        "ordo-playbook workflows show inspect-issue",
        "ordo-playbook next",
        "ordo-playbook next --graph",
        "ordo-playbook plan inspect-issue",
        "ordo-playbook --profile review plan inspect-issue",
        "ordo-playbook --input enabled=true plan inspect-issue",
        "ordo-playbook --input-file body=./prompt.md plan inspect-issue"
      ],
      "flags": [
        {
          "effect": "override_playbook_discovery",
          "name": "--file",
          "required": false,
          "summary": "Use one explicit playbook file path",
          "value_shape": "PATH"
        },
        {
          "effect": "select_active_profile",
          "name": "--profile",
          "required": false,
          "summary": "Select one named profile for this run",
          "value_shape": "NAME"
        },
        {
          "effect": "override_input_inline",
          "name": "--input",
          "repeatable": true,
          "required": false,
          "summary": "Add or override one top-level workflow input from an inline YAML value",
          "value_shape": "KEY=VALUE"
        },
        {
          "effect": "override_input_from_file",
          "name": "--input-file",
          "repeatable": true,
          "required": false,
          "summary": "Add or override one top-level workflow input from a raw UTF-8 file string",
          "value_shape": "KEY=PATH"
        },
        {
          "effect": "emit_next_state_graph",
          "name": "--graph",
          "required": false,
          "summary": "With next, show the inferred state-topology graph behind the recommendation"
        },
        {
          "effect": "emit_json",
          "name": "--json",
          "required": false,
          "summary": "Emit JSON without extra decoration"
        }
      ],
      "input_override_precedence": [
        "workflow.inputs declares the allowed activation keys; declared keys are required at activation=true",
        "profile.inputs may supply values for declared workflow inputs",
        "--input overrides workflow and profile-provided values for one run",
        "--input-file overrides workflow and profile-provided values for one run",
        "unknown activation inputs are rejected=true",
        "when both --input and --input-file set the same key, --input-file wins"
      ],
      "next_priority": [
        "prefer workflows tied to the active state-backed work context over unrelated utility workflows",
        "prefer workflows blocked only by execution-only operator input over workflows blocked by world-state mismatch",
        "keep inspection-only workflows below continuation-capable workflows when both are otherwise credible"
      ],
      "modes": [
        {
          "name": "review <workflow>",
          "summary": "review authoring-quality findings without making changes"
        },
        {
          "name": "check <workflow>",
          "summary": "check whether the workflow can be run now, without making changes"
        },
        {
          "name": "plan <workflow>",
          "summary": "show what the workflow would do, without making changes"
        },
        {
          "name": "explain <workflow>",
          "summary": "explain why the workflow can or cannot be run right now"
        },
        {
          "name": "run <workflow>",
          "summary": "run the workflow and do the real work"
        },
        {
          "name": "next",
          "summary": "suggest which workflow should run next from the current playbook context, preferring state-connected continuation over world-blocked or unrelated options"
        }
      ],
      "name": "ordo-playbook",
      "purpose": "Browse playbook workflows, ask which workflow should run next, or launch one named workflow into one runtime mode",
      "run_success_surface": "successful run emits workflow-local results, may also surface global published values, and may synthesize one top-level fallback result when neither results nor published output were produced",
      "usage": "ordo-playbook [--file PATH] [--profile NAME] [--input KEY=VALUE] [--input-file KEY=PATH] [--graph] [--json] <command>"
    }
  ],
  "document_kind": "command_line"
}
```
