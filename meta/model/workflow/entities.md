# Workflow entities

## Main entities

- `Workflow`
- `OperationRef`
- `Guard`
- `Step`
- `Profile`
- `Override`
- `Connector`
- `ConnectorBootstrap`
- `OperationContract`
- `ExecutionPlan`
- `OperationResult`
- `ExecutionResult`
- `Diagnostic`

## Key relations

- A `Workflow` contains ordered `Guard` and `Step` entries.
- A `Guard` and a `Step` reference an `OperationRef`.
- A `Connector` groups operations and can own shared bootstrap/runtime prerequisites.
- A `Profile` supplies reusable parameters or composition defaults.
- An `Override` changes resolution explicitly, never silently.
- An `OperationContract` describes public inputs, outputs, effects, and failure modes.
- An `ExecutionPlan` describes checks, steps, and blockers without requiring effectful execution.
- An `OperationResult` captures structured connector-level outcome details.
- An `ExecutionResult` contains status plus diagnostics and outputs.

## Boundary reminder

- `Workflow`, `Guard`, and `Step` express orchestration intent.
- They do not own connector implementation algorithms.
- `Profile` and `Override` express composition and explicit local adaptation.
- `Diagnostic` and execution/result entities carry machine-usable analysis and runtime surfaces.
