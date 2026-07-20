# Local expression model

## Position

Local expressions form one workflow-owned expression system with multiple contexts.

The model distinguishes:

- the shared idea of local-expression evaluation;
- context-specific restrictions on roots and timing;
- product-defined value interpretation and transformation over already available values;
- authored surface forms used by different fields.

## Shared model elements

### Context

A context determines:

- whether the expression is value-oriented or condition-oriented;
- which local roots may appear;
- whether evaluation happens in pre-execution, step-local, caller-local, or fragment-local scope;
- whether the surface is native or embedded.

It should not imply a separate read-only execution engine for otherwise equivalent probe-capable expression nodes.

### Root

A root is one documented local reference family.

The initial modeled roots are `inputs...`, `args...`, `state...`, and `step...`.

### Non-effectful observation dependency

A non-effectful observation dependency is a product-defined read-only observation that a local expression may request without changing the world.

Read-only probe calls belong to this dependency class.
They are distinct from local roots, but they may participate in the same expression tree when the surrounding context permits them.

### Scope

Scope determines where a root is meaningful.

- `inputs...` is workflow-global.
- `args...` is fragment-local.
- `state...` is runtime-state-owned and context-gated.
- `step...` is execution-local and order-sensitive.

### Context family

A context family groups surfaces by semantic job.

- condition-oriented contexts produce admission or execution conditions;
- value-oriented contexts produce local derived values.

### Derived value

A derived value is a value produced from already available local-expression inputs or prior derived values.

Derived values may flow into later local-expression operations so long as the surrounding context permits the dependencies used to produce them.

### Representation adapter

A representation adapter is a product-defined operation family for interpreting one already available value through a stable representation model.

Examples may include markdown-, html-, json-, or string-oriented operations.

An adapter operation may:

- navigate or select within a represented value;
- expose an addressable focus over part of that value for further pure local work;
- transform the represented value into a new derived value.

Such operations remain part of local value derivation rather than connector execution.

The modeled adapter shape is:

- concrete adapter families rely on one shared adapter invocation seam rather than ad hoc family-specific runtime entry points;
- adapter invocation starts one adapter-defined addressing or selection chain over an already available root value;
- the interior shape of that chain is adapter-specific rather than globally normalized;
- a terminal adapter mutation ends the chain and returns an updated root value for the represented structure.

### Canonical core

The canonical local-expression core is the shared non-effectful tree model that supports both condition-oriented and value-oriented contexts.

Its retained construct families should cover:

- literals and list values;
- local-root references and field navigation;
- read-only probe observations;
- boolean composition and comparison;
- pipelines and built-in calls;
- representation-adapter operations and their derived values.

Its excluded construct families should cover:

- effectful connector actions;
- runtime-state mutation semantics;
- hidden workflow-control structures;
- workflow-defined language extension.

### Probe-observation execution contract

Canonical local-expression evaluation may require a read-only probe observation when the tree contains a probe-call node and the surrounding context permits such observation.

The intended execution contract is:

- canonical parsing and validation produce one tree model regardless of whether a node is satisfied from local roots or from read-only observation;
- canonical evaluation may delegate probe acquisition through a dedicated read-only observation interface;
- canonical evaluation remains the owner of node semantics, context gating, caching expectations, trace shape, and diagnostics emitted for probe-call execution.

The modeled execution expectation is that one evaluation session may cache repeated equivalent read-only observation requests and that a failed read-only observation fails the surrounding expression evaluation.

This keeps probe calls inside one local-expression engine while avoiding any claim that the engine itself performs effectful connector actions.

## Surface distinction

The model separates:

- the local-expression system itself;
- the authored surface form used in one field;
- the restrictions imposed by the surrounding context.

This means an interpolation envelope, a bare condition string, and a caller-side include binding may all belong to the same modeled local-expression system even when their authored syntax differs.

## Control boundary

Local expressions may derive values and conditions.

They are not themselves the owner of:

- connector execution;
- effectful action semantics;
- hidden control-flow structure;
- runtime-state mutation semantics.

Any adapter-provided update semantics therefore describe pure value transformation only.
Persistence of a transformed value remains outside the local-expression system and belongs to workflow steps or other effectful runtime surfaces.
