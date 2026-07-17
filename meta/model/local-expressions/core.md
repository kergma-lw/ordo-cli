# Local expression model

## Position

Local expressions form one workflow-owned expression system with multiple contexts.

The model distinguishes:

- the shared idea of local-expression evaluation;
- context-specific restrictions on roots and timing;
- authored surface forms used by different fields.

## Shared model elements

### Context

A context determines:

- whether the expression is value-oriented or condition-oriented;
- which local roots may appear;
- whether evaluation happens in pre-execution, step-local, caller-local, or fragment-local scope;
- whether the surface is native or embedded.

### Root

A root is one documented local reference family.

The initial modeled roots are `inputs...`, `args...`, `state...`, and `step...`.

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
