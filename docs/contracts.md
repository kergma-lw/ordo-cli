# Ordo v0 contracts

## Workflow contract

The stable workflow shape for v0 is:

```yaml
version: 0
workflow: string
inputs: {}
guards: []
steps: []
```

Rules:

- unknown stable fields are invalid;
- `guards` are evaluated before effectful `steps`;
- `steps` order is meaningful;
- YAML is an authoring surface, not the canonical runtime model;
- loaded workflow data must remain losslessly JSON-serializable.

Machine-readable schema:

- `schema/workflow.schema.json`

## Runtime result contract

The stable runtime result envelope for v0 is JSON-shaped and must distinguish at least these statuses:

- `ok`
- `validation_error`
- `resolution_error`
- `guard_failed`
- `execution_error`

Baseline envelope fields:

- `mode`
- `status`
- `diagnostics`
- `plan`
- `outputs`
- `operation_results`
- `failed_guard`
- `failed_step`

Rules:

- blocked-before-execution must remain distinguishable from execution failure;
- machine-relevant meaning must remain available in structured fields;
- contract-level values must be losslessly JSON-serializable.

Machine-readable schema:

- `schema/runtime-result.schema.json`
