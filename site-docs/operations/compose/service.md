# compose.service

Observe one declared Compose service as an orchestration unit.

Use this when a workflow needs this exact operation surface. In practice: observe one declared Compose service as an orchestration unit.

- Namespace: `compose`
- Kind: `probe`
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
  "containers": "object",
  "declared": "boolean",
  "healthy": "boolean | null",
  "published_ports": "array[string]",
  "service": "string",
  "state": "string"
}
```

## Effects

- None

## Failure modes

- `service_not_declared`
- `project_invalid`
- `orchestrator_unavailable`
- `observation_failed`

## Requirements

- None

## Example inputs

### `compose.service`

```json
{
  "service": "api"
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
    "effects": [],
    "examples": [
      {
        "inputs": {
          "service": "api"
        },
        "reference": "compose.service"
      }
    ],
    "failure_modes": [
      "service_not_declared",
      "project_invalid",
      "orchestrator_unavailable",
      "observation_failed"
    ],
    "inputs": {
      "service": "string"
    },
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "service",
    "outputs": {
      "containers": "object",
      "declared": "boolean",
      "healthy": "boolean | null",
      "published_ports": "array[string]",
      "service": "string",
      "state": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Observe one declared Compose service as an orchestration unit.",
    "tags": [
      "compose",
      "probe"
    ]
  },
  "operation_name": "service",
  "reference": "compose.service",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
