# Package layout

## v0 Python package shape

The minimal v0 package layout is:

- `ordo.model` — public domain models for workflow, profile, connector, diagnostic, and runtime result.
- `ordo.runtime` — runtime orchestration entry points and mode-specific logic.
- `ordo.connectors` — public connector family implementations and registries.
- `ordo.types` — shared JSON-shaped value aliases used by public model surfaces.

## Model split inside `ordo.model`

- `workflow` owns `Workflow`, `OperationRef`, `Guard`, and `Step`.
- `profile` owns `Profile` and explicit `Override` data.
- `connector` owns `Connector`, family bootstrap data, and `OperationContract`.
- `diagnostic` owns normalized machine-usable diagnostics.
- `runtime` owns runtime mode, plan, operation result, and result envelope data.

## Boundary rule

Package layout must preserve the contract boundary:

- workflow models hold orchestration intent;
- connector models hold public operation contracts;
- runtime models hold decision and result surfaces;
- helper modules must not smuggle hidden runtime semantics into the model layer.

## v0 discipline

- The layout must stay small enough to explain directly from the public contract.
- It must support YAML authoring and JSON-shaped runtime surfaces.
- It must support `check`, `plan`, `execute`, and `explain` without treating connector authoring as the routine customization path.
