# Workflow entities

## Main entities

- `Playbook`
- `Workflow`
- `WorkflowFragment`
- `FragmentArg`
- `StateNeed`
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

- A `Playbook` names project-local workflow entries, profile entries, and runtime state declarations.
- A `Workflow` contains ordered `Guard` and `Step` entries.
- A `Workflow` may include reusable `WorkflowFragment` instances through ordered include items inside its block structure.
- A `WorkflowFragment` may declare local `FragmentArg` entries and workflow payload content.
- A `Workflow` may declare logical `StateNeed` entries that are bound by the active playbook workflow entry.
- A `Guard` references an `OperationRef`.
- A `Step` is either an operation-call step that references an `OperationRef` or a built-in runtime step form.
- A `Step` may declare an `if` condition that controls whether that one declared step executes or is skipped.
- A `Step` may publish an execution-local registered result for later steps through a workflow-local `register` identifier.
- A `Connector` groups operations and can own shared bootstrap/runtime prerequisites.
- A `Profile` supplies reusable parameters or composition defaults.
- An `Override` changes resolution explicitly, never silently.
- An `OperationContract` describes public inputs, outputs, effects, and failure modes.
- An `ExecutionPlan` describes checks, steps, and blockers without requiring effectful execution.
- An `OperationResult` captures structured connector-level outcome details.
- An `ExecutionResult` contains status plus diagnostics and outputs.

## Boundary reminder

- `Playbook` expresses project-local launch intent and resolution context.
- `Workflow`, `Guard`, and `Step` express orchestration intent.
- `StateNeed` expresses workflow-level need for persistent state without naming concrete project storage instances.
- Step conditions express per-step eligibility, not first-class branch topology.
- Built-in runtime step forms may be effectful, such as state mutation, or pure, such as value materialization.
- Registered step results express execution-local data flow, not persistent workflow state.
- Fragment arguments express local reusable-fragment binding, not global workflow input redefinition.
- Included-fragment boundaries keep registered `step...` data local unless a later explicit export surface is introduced.
- They do not own connector implementation algorithms.
- `Profile` and `Override` express composition and explicit local adaptation.
- `Diagnostic` and execution/result entities carry machine-usable analysis and runtime surfaces.
