# Workflow entities

## Main entities

- `Workflow`
- `Connector`
- `OperationRef`
- `Guard`
- `Step`
- `Profile`
- `Override`
- `ExecutionPlan`
- `ExecutionResult`
- `Diagnostic`

## Key relations

- A `Workflow` contains ordered `Guard` and `Step` entries.
- A `Guard` and a `Step` reference an `OperationRef`.
- A `Connector` groups operations and can own shared bootstrap/runtime prerequisites.
- A `Profile` supplies reusable parameters or composition defaults.
- An `Override` changes resolution explicitly, never silently.
- An `ExecutionResult` contains status plus diagnostics and outputs.
