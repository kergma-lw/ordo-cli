# Workflow entities

## Main entities

- `Playbook`
- `Workflow`
- `WorkflowFragment`
- `FragmentArg`
- `FragmentRun` (planned)
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
- A future `Workflow` surface may invoke reusable `WorkflowFragment` instances through ordered `run` step forms inside `steps` blocks.
- A future `Workflow` surface may also express bounded `for_each` on `run` for repeated fragment invocation or repeated inline short `steps` bodies.
- A `WorkflowFragment` may declare local `FragmentArg` entries and workflow payload content.
- A planned `FragmentRun` would express runtime-scoped invocation of one reusable `WorkflowFragment` with an explicit caller/callee boundary while still reading like one workflow step.
- A planned bounded fan-out `FragmentRun` would still remain one workflow step with one explicit repeated-body boundary rather than a general looping language.
- A `Workflow` may declare logical `StateNeed` entries that are bound by the active playbook workflow entry.
- A `Guard` references an `OperationRef`.
- A `Step` is either an operation-call step that references an `OperationRef` or a built-in runtime step form.
- A `Step` may declare an `if` condition that controls whether that one declared step executes or is skipped.
- A `Step` may publish an execution-local registered result for later steps through a workflow-local `register` identifier.
- A `run` step may expose callee workflow-local `results` back to caller-local `step...` reads through that same `register` surface.
- A future fan-out `run` step may expose one array of per-iteration callee workflow-local `results` payloads through that same outer `register` surface.
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
- Workflow-local `result` values and run-session-global `publish` values are distinct result channels with different scopes.
- Fragment arguments express local reusable-fragment binding, not global workflow input redefinition.
- Static include expansion keeps one assembled workflow-local `step...` namespace across inline and included steps.
- A future fragment-run boundary should keep caller-local and callee-local `step...` data separated unless an explicit transfer surface is introduced.
- A future inline repeated-body boundary should keep inner step registers iteration-local rather than widening them into caller-global names.
- They do not own connector implementation algorithms.
- `Profile` and `Override` express composition and explicit local adaptation.
- `Diagnostic` and execution/result entities carry machine-usable analysis and runtime surfaces.
