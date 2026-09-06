# compose.start

Bring one Compose project or service into operational running state.

Use this when a workflow needs this exact operation surface. In practice: bring one Compose project or service into operational running state.

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

- bring the requested Compose target into operational running state

## Failure modes

- `service_not_declared`
- `project_invalid`
- `orchestrator_unavailable`
- `image_unavailable`
- `build_failed`
- `dependency_failed`
- `runtime_start_failed`
- `healthcheck_failed`
- `start_failed`

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

### `compose.start`

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
      "bring the requested Compose target into operational running state"
    ],
    "examples": [
      {
        "inputs": {
          "service": "string | null"
        },
        "reference": "compose.start"
      }
    ],
    "failure_modes": [
      "service_not_declared",
      "project_invalid",
      "orchestrator_unavailable",
      "image_unavailable",
      "build_failed",
      "dependency_failed",
      "runtime_start_failed",
      "healthcheck_failed",
      "start_failed"
    ],
    "inputs": {
      "service": "string | null"
    },
    "invalidates_observations": [
      "compose.*"
    ],
    "kind": "action",
    "maturity": "stable",
    "name": "start",
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
    "summary": "Bring one Compose project or service into operational running state.",
    "tags": [
      "compose",
      "action"
    ]
  },
  "operation_name": "start",
  "reference": "compose.start",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
