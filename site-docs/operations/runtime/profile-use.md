# runtime.profile.use

Switch the runtime execution profile for later work in the current run.

Use this for runtime-level compatibility or execution-context work. In practice: switch the runtime execution profile for later work in the current run.

- Namespace: `runtime`
- Kind: `action`
- Maturity: `stable`
- Deprecated: `true`

## Related commands

- `capabilities` — `ordo-help capabilities --json`
- `operations` — `ordo-help operations --json`

## Inputs

```json
{
  "profile": "string"
}
```

## Outputs

```json
{
  "profile": "string"
}
```

## Effects

- switch runtime profile for later execution in the current run

## Failure modes

- `input_error`
- `execution_error`

## Requirements

- None

## Example inputs

### `runtime.profile.use`

```json
{
  "profile": "string"
}
```

## Full JSON reference

```json
{
  "bootstrap": {
    "context_fields": [],
    "prerequisites": []
  },
  "document_kind": "operation",
  "namespace": "runtime",
  "operation": {
    "deprecated": true,
    "effects": [
      "switch runtime profile for later execution in the current run"
    ],
    "examples": [
      {
        "inputs": {
          "profile": "string"
        },
        "reference": "runtime.profile.use"
      }
    ],
    "failure_modes": [
      "input_error",
      "execution_error"
    ],
    "inputs": {
      "profile": "string"
    },
    "invalidates_observations": [],
    "kind": "action",
    "maturity": "stable",
    "name": "profile.use",
    "outputs": {
      "profile": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [
      "workflow.step.profile_switch"
    ],
    "summary": "Legacy compatibility action for switching runtime execution to another declared profile",
    "tags": [
      "runtime",
      "action"
    ]
  },
  "operation_name": "profile.use",
  "reference": "runtime.profile.use",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
