# Product shape

## Layers

### 1. `workflows/`

Declarative scenarios.

They contain:
- intent;
- guards;
- steps;
- references to connector operations;
- minimal local logic.

They do not contain:
- complex algorithms;
- hidden shell magic as the primary mechanism;
- project-specific code when it can be moved into a profile or an operation.

### 2. `connectors/`

Public connector families and their operations.

Workflow files rely on them directly.

A connector family provides:
- shared bootstrap/context;
- a shared operation space;
- family-level prerequisites and diagnostics.

An operation is:
- a stable useful operation;
- with explicit input;
- with explicit semantics;
- with a structured result.

### 3. `profiles/`

Compositional sets of parameters and presets.

Examples:
- verify profile;
- default repo policy;
- parameter sets for common scenarios.

These are a primary authoring surface for both humans and agents.

### 4. `schema/`

Machine-readable contract.

### 5. `docs/`

Public format documentation.

### 6. `meta/`

Internal project support: decisions, invariants, and model.

## Boundary

Ordo is primarily a runtime and contract layer.

The most important project boundary is:
- orchestration and policy belong in declarations;
- non-trivial computation and transformation belong in connector operation code.

Another important product boundary is:
- workflow and profile authoring are expected and common;
- connector authoring is a higher-cost extension path and not the default way to adapt a project.
