# compose.stop

Stop one Compose project or service.

Use this when a workflow needs this exact operation surface. In practice: stop one Compose project or service.

- Namespace: `compose`
- Kind: `action`
- Maturity: `stable`
- Deprecated: `false`

## Related commands

- `capabilities` — `ordo-help capabilities --json`
- `operations` — `ordo-help operations --json`

## Inputs

```json
{
  "service": "string | null"
}
```

## Outputs

```json
{
  "changed": "boolean",
  "changed_services": "array[string]",
  "state": "string",
  "target": "string",
  "target_kind": "string"
}
```

## Effects

- stop the requested Compose target

## Failure modes

- `service_not_declared`
- `project_invalid`
- `orchestrator_unavailable`
- `dependency_stop_blocked`
- `runtime_stop_failed`
- `stop_failed`

## Requirements

- None

## Preflight observations

```json
[
  {
    "probe": "compose.project",
    "with": {}
  }
]
```

## Invalidated observations

- `compose.*`

## Example inputs

### `compose.stop`

```json
{
  "service": "string | null"
}
```

## Full JSON reference

```json
{
  "bootstrap": {
    "context_fields": [
      "project_directory",
      "compose_file",
      "project_name"
    ],
    "prerequisites": [
      "docker compose available"
    ]
  },
  "document_kind": "operation",
  "namespace": "compose",
  "operation": {
    "deprecated": false,
    "effects": [
      "stop the requested Compose target"
    ],
    "examples": [
      {
        "inputs": {
          "service": "string | null"
        },
        "reference": "compose.stop"
      }
    ],
    "failure_modes": [
      "service_not_declared",
      "project_invalid",
      "orchestrator_unavailable",
      "dependency_stop_blocked",
      "runtime_stop_failed",
      "stop_failed"
    ],
    "inputs": {
      "service": "string | null"
    },
    "invalidates_observations": [
      "compose.*"
    ],
    "kind": "action",
    "maturity": "stable",
    "name": "stop",
    "outputs": {
      "changed": "boolean",
      "changed_services": "array[string]",
      "state": "string",
      "target": "string",
      "target_kind": "string"
    },
    "preflight_observations": [
      {
        "probe": "compose.project",
        "with": {}
      }
    ],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Stop one Compose project or service.",
    "tags": [
      "compose",
      "action"
    ]
  },
  "operation_name": "stop",
  "reference": "compose.stop",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
