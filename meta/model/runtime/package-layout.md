# Package layout

## v0 Python package shape

The minimal v0 package layout is:

- `ordo.model` — public domain models for workflow, profile, connector, diagnostic, and runtime result.
- `ordo.runtime` — runtime orchestration entry points and mode-specific logic.
- `connectors` — built-in public connector library packages, organized by family.
- `ordo.connectors` — runtime-facing adapter and registry surface over the built-in connector library.
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

## Connector library shape

The built-in connector library should live under the repository-level `connectors/` tree.

`ordo.connectors` may provide adapter and registry entry points for the runtime, but it should not become the primary home of family implementations.
The runtime core should reach built-in connectors through provider-style wiring, not through a hardcoded assumption about where family code lives.

A separate composition layer should decide whether the standard built-in connector provider is installed by default for a particular application surface.

Even when connector code is imported through `ordo.connectors`, the conceptual boundary remains:

- `ordo.runtime` is the engine and orchestration layer;
- `connectors` is the built-in public connector library consumed by the runtime;
- `ordo.connectors` is the runtime-facing adapter surface over that library.

The import path may be package-local for implementation convenience, but that should not blur ownership of connector semantics.
Built-in connectors should not be modeled as part of the runtime core merely because they are shipped with the same distribution.

Connector packages should follow the family-first layout:

- `connectors/<family>/bootstrap.py` for family-level bootstrap;
- `connectors/<family>/probes/<operation>.py` for a single public probe module;
- `connectors/<family>/actions/<operation>.py` for a single public action module.

This layout should be preferred over monolithic cross-family modules and over hand-maintained central registries that duplicate operation declarations outside the family package tree.

Assembly should prefer family-local autodiscovery or an equivalent family-local mechanism rather than a cross-family hand-edited registry list.
