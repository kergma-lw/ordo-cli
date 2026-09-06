# compose.remove

Remove one stopped materialized Compose service instance.

Use this when a workflow needs this exact operation surface. In practice: remove one stopped materialized Compose service instance.

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
  "service": "string"
}
```

## Outputs

```json
{
  "changed": "boolean",
  "state": "string",
  "target": "string",
  "target_kind": "string"
}
```

## Effects

- remove the materialized runtime instance for one Compose service

## Failure modes

- `service_not_declared`
- `service_running`
- `project_invalid`
- `orchestrator_unavailable`
- `runtime_remove_failed`
- `remove_failed`

## Requirements

- None

## Preflight observations

```json
[
  {
    "probe": "compose.service",
    "with": {
      "service": "{service}"
    }
  }
]
```

## Invalidated observations

- `compose.*`

## Example inputs

### `compose.remove`

```json
{
  "service": "string"
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
      "remove the materialized runtime instance for one Compose service"
    ],
    "examples": [
      {
        "inputs": {
          "service": "string"
        },
        "reference": "compose.remove"
      }
    ],
    "failure_modes": [
      "service_not_declared",
      "service_running",
      "project_invalid",
      "orchestrator_unavailable",
      "runtime_remove_failed",
      "remove_failed"
    ],
    "inputs": {
      "service": "string"
    },
    "invalidates_observations": [
      "compose.*"
    ],
    "kind": "action",
    "maturity": "stable",
    "name": "remove",
    "outputs": {
      "changed": "boolean",
      "state": "string",
      "target": "string",
      "target_kind": "string"
    },
    "preflight_observations": [
      {
        "probe": "compose.service",
        "with": {
          "service": "{service}"
        }
      }
    ],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Remove one stopped materialized Compose service instance.",
    "tags": [
      "compose",
      "action"
    ]
  },
  "operation_name": "remove",
  "reference": "compose.remove",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
