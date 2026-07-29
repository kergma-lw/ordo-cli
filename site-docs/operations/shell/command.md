# shell.command

Run a shell command.

Use this only when a low-level shell surface is truly required. In practice: run a shell command.

- Namespace: `shell`
- Kind: `action`
- Maturity: `stable`
- Deprecated: `false`

## Related commands

- `capabilities` — `ordo-help capabilities --json`
- `operations` — `ordo-help operations --json`

## Inputs

```json
{
  "command": "string"
}
```

## Outputs

```json
{
  "exit_code": "integer",
  "stderr": "string",
  "stdout": "string"
}
```

## Effects

- execute shell command

## Failure modes

- `command_failed`
- `action_failed`

## Requirements

- None

## Example inputs

### `shell.command`

```json
{
  "command": "string"
}
```

## Full JSON reference

```json
{
  "bootstrap": {
    "context_fields": [
      "shell",
      "working_directory"
    ],
    "prerequisites": [
      "supported shell available"
    ]
  },
  "document_kind": "operation",
  "namespace": "shell",
  "operation": {
    "deprecated": false,
    "effects": [
      "execute shell command"
    ],
    "examples": [
      {
        "inputs": {
          "command": "string"
        },
        "reference": "shell.command"
      }
    ],
    "failure_modes": [
      "command_failed",
      "action_failed"
    ],
    "inputs": {
      "command": "string"
    },
    "invalidates_observations": [],
    "kind": "action",
    "maturity": "stable",
    "name": "command",
    "outputs": {
      "exit_code": "integer",
      "stderr": "string",
      "stdout": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Action operation 'shell.command'",
    "tags": [
      "shell",
      "action"
    ]
  },
  "operation_name": "command",
  "reference": "shell.command",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
