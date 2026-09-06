# compose.project

Observe one Compose project as an orchestration unit.

Use this when a workflow needs this exact operation surface. In practice: observe one Compose project as an orchestration unit.

- Namespace: `compose`
- Kind: `probe`
- Maturity: `stable`
- Deprecated: `false`

## Related commands

- `capabilities` — `ordo-help capabilities --json`
- `operations` — `ordo-help operations --json`

## Inputs

```json
{}
```

## Outputs

```json
{
  "declared_services": "array[string]",
  "project": "string",
  "service_counts": "object",
  "services": "object",
  "state": "string"
}
```

## Effects

- None

## Failure modes

- `project_invalid`
- `orchestrator_unavailable`
- `observation_failed`

## Requirements

- None

## Example inputs

### `compose.project`

```json
{}
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
        "inputs": {},
        "reference": "compose.project"
      }
    ],
    "failure_modes": [
      "project_invalid",
      "orchestrator_unavailable",
      "observation_failed"
    ],
    "inputs": {},
    "invalidates_observations": [],
    "kind": "probe",
    "maturity": "stable",
    "name": "project",
    "outputs": {
      "declared_services": "array[string]",
      "project": "string",
      "service_counts": "object",
      "services": "object",
      "state": "string"
    },
    "preflight_observations": [],
    "prerequisites": [],
    "replaced_by": [],
    "summary": "Observe one Compose project as an orchestration unit.",
    "tags": [
      "compose",
      "probe"
    ]
  },
  "operation_name": "project",
  "reference": "compose.project",
  "related_commands": {
    "capabilities": "ordo-help capabilities --json",
    "operations": "ordo-help operations --json"
  }
}
```
