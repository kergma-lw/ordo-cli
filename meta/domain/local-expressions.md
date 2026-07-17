# Local expressions domain

## Role

Local expressions are the workflow-owned declarative surface for reading local workflow-visible data and deriving local conditions or values without introducing connector execution, hidden imperative logic, or a second orchestration layer.

They exist to keep small workflow-local computation and condition declaration inside the public authoring surface.

## What this domain owns

This domain owns:

- the idea that workflows may carry expression-bearing fields;
- the local data surfaces that expressions may read;
- the semantic distinction between expression contexts;
- the boundary between local expression evaluation and connector operation execution;
- the boundary between local expression evaluation and workflow control surfaces.

This domain does not own exact grammar, parser structure, `${...}` envelope rules, or YAML field shape details.

## Core entities

### Local expression

A local expression is a workflow-visible declarative expression whose meaning stays within local workflow semantics.

It may read documented local surfaces and derive a value or condition, but it must not become a hidden scripting layer.

### Expression context

An expression context is one product surface in which local expressions may appear.

Different contexts may permit different roots, evaluation timing, and restrictions while still belonging to one local-expression domain.

### Expression root

An expression root is a documented workflow-visible surface that an expression may read.

The initial local-expression roots are:

- `inputs...` — declared workflow inputs;
- `args...` — included-fragment arguments local to one fragment instance;
- `state...` — documented runtime-state read surface when the surrounding context allows state access;
- `step...` — prior registered step results when the surrounding context allows execution-local step data.

## Core contexts

### Guard context

Guard context is the pre-execution policy context.

Its job is to express whether execution may proceed before effectful business steps run.

Because of that role, guard context is limited to dependencies that are known at launch time and must remain compatible with read-only, pre-execution analysis.

### Step-condition context

Step-condition context is the step-local conditional execution surface.

It is still workflow-owned condition evaluation, but it is not the same semantic job as guard context because it may depend on execution-local information that appears only after earlier steps run.

### Include-binding context

Include bindings belong to the local-expression domain because they may evaluate caller-scoped local expressions before fragment-local `args...` are bound.

Their semantic job is caller-side value binding for assembly-expanded material, not connector invocation.

### Embedded value context

Embedded value context covers value-bearing fields that reuse local-expression evaluation.

It may depend on whatever is available at the point where that value is resolved, but it remains a pure local-expression surface rather than a hidden execution or control surface.

## Context families

Local-expression contexts divide into two families:

- condition-oriented contexts such as guards and step conditions;
- value-oriented contexts such as embedded value fields and include bindings.

## Boundary discipline

### Expression versus connector execution

Local expressions may read documented workflow-visible data.

They must not themselves become a public connector invocation surface for effectful work.

Any connector execution semantics belong to connector operations and workflow steps, not to local expressions as such.

### Expression versus workflow control

Local expressions may derive values and conditions.

They must not silently absorb broader workflow control semantics such as branching structure, looping, or hidden execution planning.

### Expression versus storage ownership

`state...` is a read surface inside local expressions when the surrounding context allows it.

That does not make local expressions the semantic owner of runtime state.

### Expression versus execution-local data

`step...` is execution-local.

It may appear only in contexts whose semantics legitimately depend on prior step execution.

It must not be treated as a universally available root across all expression contexts.

In particular, pre-execution policy context must not depend on execution-local `step...` data.

## Tree-wide context discipline

Context restrictions apply to the whole local-expression tree, not only to the root term.

An expression context therefore cannot regain a forbidden dependency class merely by nesting it inside a call argument, list item, comparison, or other subexpression.

## Review standard

A good local-expression surface should let a reader tell:

- what local data is being read;
- whether the expression is producing a value or a condition;
- whether the context is pre-execution, step-local, fragment-local, or caller-local;
- whether a dependency is global, fragment-local, state-backed, or execution-local.

If these distinctions are hard to recover, expression semantics are drifting out of the documented product surface.

## Related domain docs

- workflow semantics: `domain/workflow.md`
- policy semantics: `domain/policy.md`
- authoring semantics: `domain/authoring.md`
