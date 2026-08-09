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

Equivalent contexts should therefore remain stable across structural nesting.

If one read-only step-local authored surface is observation-capable at top level, the same semantic context should remain observation-capable inside nested inline `steps`, inside one inline `for_each` body, and inside reusable fragment bodies unless a distinct higher-level rule explicitly changes the semantic class of the surface.

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

### Collection-shaping filter

A collection-shaping filter is a product-defined pipeline filter that reshapes already available JSON-shaped values without introducing a per-item expression sublanguage or hidden workflow control semantics.

The initial modeled collection-shaping filter set is:

- `field(path)`;
- `only(field=value)` / `only(field!=value)`;
- `flatten`;
- `first`;
- `last`;
- `length`;
- `unique`.

These filters exist to cover common workflow-local normalization needs such as extracting one field from a step-result collection, collapsing one nesting level, selecting one edge item, counting entries, or removing duplicate JSON values.

### Workflow-local binding

A workflow-local binding is one authored `let` entry that gives a local expression a workflow-scoped name.

The modeled binding shape is:

- the binding name is workflow-local rather than global or inherited;
- the binding value is one ordinary local-expression tree rather than a text substitution;
- the binding is immutable for the duration of the workflow run;
- the binding may reference documented roots and other dependencies that are otherwise valid for the surrounding expression system;
- the binding may not reference another `let` binding;
- the binding does not create a new context and does not widen which dependencies are legal at one use site.

The modeled validation rule is that a `let` binding is accepted only where the equivalent inline expression would be accepted by the surrounding authored context.

### Presence check

A presence check is one product-defined boolean helper that asks whether one approved lookup-like argument is observably available without collapsing unrelated evaluation failures into boolean absence.

The narrow modeled argument classes are:

- lookup-style references whose missingness semantics are defined by the surrounding root contract;
- read-only representation-adapter invocations whose absence semantics are defined by adapter `not_found`.

For read-only adapter invocation arguments, the modeled interpretation is:

- successful invocation means present;
- adapter `not_found` means missing;
- any other adapter failure remains a real evaluation failure.

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

### Pipeline filter

A pipeline filter is one product-defined operation applied to an already evaluated local-expression value.

The modeled pipeline shape is:

- the left side supplies one already evaluated input value;
- the filter name selects one product-defined filter contract;
- optional filter arguments are themselves local-expression values evaluated under the surrounding context policy;
- the filter result becomes the next pipeline value.

The modeled input discipline is intentionally broad:

- a pipeline input value may be any ordinary local-expression value such as a string, number, boolean, null, list, object, local-root lookup result, probe result, or prior derived value;
- individual filter contracts, rather than the pipeline surface itself, determine which input shapes are accepted.

The modeled filter families include:

- transforming filters such as `lower`, `trim`, and `slug`;
- boolean comparison filters such as `eq(...)` and `ne(...)`;
- boolean predicate filters such as `is_string`, `is_number`, `is_integer`, and `is_boolean`;
- boolean membership filters such as `in(container)`;
- bounded collection-selection filters such as `only(field=value)` and `only(field!=value)`;
- boolean negation filters such as `not`;
- collection-shaping filters such as `field(path)`, `lookup(key)`, `flatten`, `first`, `last`, `length`, and `unique`.

The modeled predicate-filter semantics are:

- predicate filters consume one already evaluated input value;
- predicate filters return only boolean results;
- predicate filters do not implicitly coerce input values into another type before deciding the result.

The modeled membership-filter semantics are:

- `in(container)` consumes one already evaluated input value and one already evaluated container argument;
- the container argument must evaluate to a list value;
- membership is determined by strict element comparison without implicit coercion;
- a non-list container remains a filter misuse failure rather than a false result.

The modeled collection-shaping semantics are:

- collection-shaping filters operate only on already evaluated JSON-shaped values;
- they remain pure value transformations and do not introduce a nested item-scope expression model by themselves;
- each filter contract explicitly defines which input shapes are accepted and whether missing data becomes `null` or a failure;
- collection-shaping filters fail on unsupported input shapes rather than applying implicit coercion.

The modeled `only(...)` semantics are:

- input must be an array;
- the authored predicate is one bounded field comparison using either `field=value` or `field!=value`;
- each item is matched only when the addressed field path exists on that item;
- a missing addressed field path on one item yields a non-match rather than a whole-filter failure;
- the filter returns one array containing the kept original items in encounter order.

The modeled `field(path)` semantics are:

- object input returns the addressed field value;
- object input with a missing addressed path fails;
- array input returns an array of per-item addressed values;
- a missing addressed path within one array element yields `null` for that element rather than failing the whole projection;
- scalar or `null` input fails;
- the initial path model supports dotted field navigation and zero-based list indexing such as `results` and `results[0]`.

The modeled `lookup(key)` semantics are:

- input must be an object;
- the authored argument must evaluate to a string key;
- lookup is exact-key retrieval rather than path traversal;
- object input returns the value stored under that exact key;
- object input with a missing key fails;
- array, scalar, or `null` input fails.

The modeled `flatten` semantics are:

- input must be an array;
- flattening removes exactly one nesting level;
- non-array input fails.

The modeled `first` and `last` semantics are:

- input must be an array;
- empty-array input yields `null`;
- non-array input fails.

The modeled `length` semantics are:

- array input yields item count;
- object input yields key count;
- string input yields character count;
- other input shapes fail.

The modeled `unique` semantics are:

- input must be an array;
- output preserves encounter order and keeps the first occurrence of each value;
- equality uses normalized JSON value equality without implicit coercion;
- object key order is ignored for equality;
- array element order remains significant for equality;
- numerically distinct forms such as `1` and `1.0` remain distinct.

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

A workflow-level `let` surface therefore adds one more authored way to name local expressions without creating a second expression family or second execution engine.

## Control boundary

Local expressions may derive values and conditions.

They are not themselves the owner of:

- connector execution;
- effectful action semantics;
- hidden control-flow structure;
- runtime-state mutation semantics.

Any adapter-provided update semantics therefore describe pure value transformation only.
Persistence of a transformed value remains outside the local-expression system and belongs to workflow steps or other effectful runtime surfaces.
