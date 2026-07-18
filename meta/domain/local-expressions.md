# Local expressions domain

## Role

Local expressions are the workflow-owned declarative surface for reading local workflow-visible data and deriving local conditions or values without introducing connector execution, hidden imperative logic, or a second orchestration layer.

They exist to keep small workflow-local computation and condition declaration inside the public authoring surface.

## What this domain owns

This domain owns:

- the idea that workflows may carry expression-bearing fields;
- the local data surfaces that expressions may read;
- the idea that expressions may derive intermediate values from already available values;
- product-defined representation adapters for pure value interpretation and transformation;
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

### Read-only probe observation

A local expression may also depend on product-defined read-only connector observations when the surrounding context allows non-effectful external observation.

Such observation remains part of local-expression semantics only when it is read-only, reviewable, and does not introduce effectful connector execution.

### Derived intermediate value

A local expression may derive one value from another already available value and then continue evaluation over that derived value.

Such intermediate values remain inside local-expression semantics.
They do not by themselves introduce connector execution, workflow control, or storage ownership.

### Representation adapter

A representation adapter is a product-defined local-expression surface for interpreting an already available value through a specific representation such as markdown, html, json, or string.

Representation adapters may expose pure navigation and transformation operations over those values.
They are not connectors and they do not own external integration semantics.

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
They may also derive additional values from those already available values through pure local operations.
They may depend on read-only connector observations when those observations are modeled as non-effectful expression dependencies.

They must not themselves become a public connector invocation surface for effectful work.

Any connector execution semantics belong to connector operations and workflow steps, not to local expressions as such.

### Canonical core direction

The canonical local-expression core should keep only non-effectful observation and value-derivation semantics.

That core includes stable value and condition constructs such as:

- literals and lists;
- local roots and their field navigation;
- read-only probe observations;
- boolean composition and comparison;
- pipelines, built-ins, and representation-adapter operations.

It excludes:

- effectful connector actions;
- hidden workflow control;
- workflow-defined language extension.

### Canonical probe-call execution boundary

Read-only probe-call semantics should remain inside the canonical local-expression execution model, but they do not collapse into ordinary local-value lookup.

The intended split is:

- the canonical engine owns parsing, canonical AST shape, context policy, dependency analysis, and the node-level meaning of read-only probe-call expressions;
- runtime probe providers own the actual external observation work needed to satisfy a read-only probe call;
- expression evaluation may therefore request a read-only observation through an engine-facing probe-observation interface without thereby becoming an effectful action surface.

Implications:

- a probe call is still one canonical local-expression node, not a second expression language hidden beside the main engine;
- probe-call caching, diagnostics, and trace behavior belong to the canonical execution model even when the observed value comes from a provider surface;
- contexts that forbid non-effectful external observation must reject probe-call nodes through normal context policy rather than through ad hoc runtime split behavior.

### Expression versus value adaptation

Representation adapters belong to local-expression value derivation rather than to connector execution.

Implications:

- adapter operations may interpret, navigate, select, normalize, and transform already available values;
- adapter operations may return derived values or addressable focus values for further pure local use;
- adapter update-style operations must still return new derived values rather than persisting changes by themselves;
- any persistence of such derived values happens only when a workflow step passes the resulting value into an effectful operation.

### Expression versus workflow control

Local expressions may derive values and conditions.

They must not silently absorb broader workflow control semantics such as branching structure, looping, or hidden execution planning.

### Expression versus user-defined extensibility

Representation-adapter operations must belong to the stable product contract.

Workflows must not define their own expression functions, operators, macros, or adapter families.

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
