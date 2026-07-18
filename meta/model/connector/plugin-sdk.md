# Connector plugin SDK sketch

## Role

The connector plugin SDK is the concrete authoring-facing surface that should realize the connector authoring boundary.

It exists to let operation files stay small, local, and readable without importing core runtime models directly.

## Design goal

For a simple operation such as `git.branch`, the SDK should allow a single-file implementation that:

- declares its operation contract locally;
- executes narrow local integration work;
- returns a structured local outcome;
- avoids unnecessary incidental technical ceremony.

Simple operation files should not need avoidable scaffolding such as broad runtime-shaped arguments or unnecessary `from __future__ import annotations` imports.

## Minimal SDK entities

The SDK should expose only a small set of authoring-facing entities.

At minimum:

- operation metadata type for probes;
- operation metadata type for actions;
- uniform publication-hook return type for operation modules;
- narrow operation context type;
- structured operation outcome type;
- structured local diagnostic type;
- reusable local integration helper result types where needed.

The SDK should prefer one small coherent surface over many narrowly sliced helper types.

## Metadata expectations

Operation metadata should let an authored module declare at least:

- operation name;
- operation kind;
- inputs when applicable;
- outputs;
- failure modes;
- effects when applicable.

Metadata should remain local to the operation module rather than requiring a second hand-maintained registry declaration elsewhere.

The SDK should support a uniform publication hook such as `info()` that returns the published operation definition for the module.

That published definition should bind operation metadata and execution handler explicitly.

## Context expectations

The operation context should stay narrow and authoring-oriented.

At minimum it should support:

- operation-local input access;
- reusable command execution for command-backed operations;
- inline failure mapping for repetitive transport-level failures;
- narrow execution-environment access when needed for local behavior or diagnostics;
- explicit access to shared family bootstrap state or shared capability context when the operation depends on it.

The context should not require small operations to know workflow internals, guard-context expression internals, or runtime mode state.

When operation-to-operation reuse is allowed, the SDK should prefer an explicit local dependency surface over hidden runtime magic.

## Command helper expectations

Command-backed operations are expected to be common.

The SDK should therefore provide a command helper that:

- executes a command locally;
- normalizes repetitive transport-level failure categories;
- supports inline failure mapping close to the call site;
- returns a structured helper result suitable for local domain-specific checks after the command succeeds technically.

This helper exists to avoid repeated low-level `if` ladders for command spawn failure, non-zero exit handling, and similar transport concerns.

## Outcome expectations

The SDK outcome type should preserve the minimal structured operation outcome surface already defined elsewhere in meta:

- `status`;
- `summary`;
- `outputs`;
- `diagnostics`;
- `raw`.

The SDK may provide convenience constructors or helpers for common success and failure cases, but those helpers must not hide the structured outcome model itself.

For example, a helper that constructs a single structured diagnostic together with a failure outcome is a good fit for the SDK when it reduces repeated boilerplate across many operations without inventing a second failure abstraction.

## Low-ceremony requirement

The SDK should optimize for low incidental ceremony in small operation files.

Implications:

- simple probes and actions should fit comfortably in one small file;
- import surfaces should stay small;
- common success and failure paths should be concise;
- repeated one-diagnostic failure shaping should not require each operation to rebuild the same local helper function;
- publication should remain explicit without requiring ad hoc module-global binding conventions;
- operation code should remain more prominent than authoring-framework boilerplate.

## Runtime boundary

The SDK is not a second runtime.

It should not re-expose:

- workflow orchestration semantics;
- runtime mode semantics;
- full runtime result-envelope assembly;
- policy evaluation logic.

Those remain runtime responsibilities.

## Dependency-layer boundary

The SDK should help keep three layers distinct:

- family bootstrap and shared capability state;
- explicit operation-to-operation reuse;
- workflow-level policy composition.

It should not encourage simple technical prerequisites to masquerade as arbitrary public probe graphs, and it should not hide derived-operation dependencies behind opaque runtime behavior.

## Expected migration use

The first migration step should be able to prove the SDK shape on one or two very small operations before broader connector migration begins.

If the resulting operation code is not visibly simpler and more local than the current runtime-shaped form, the SDK shape should be reconsidered before wider adoption.

The concrete first-spike API proposal should live in a separate model document so code work can implement the SDK without reconstructing it from principles alone.

Executable family bootstrap should likewise have its own concrete model document so shared prerequisite evaluation can be implemented explicitly rather than inferred from metadata-only bootstrap declarations.
