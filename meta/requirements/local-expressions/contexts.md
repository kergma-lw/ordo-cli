# Local expression context requirements

## Expression-first value context

- Expression-first value contexts may use local expressions to derive one value for a surrounding field.
- Expression-first value contexts may read `inputs...`.
- Expression-first value contexts may read `args...` when evaluated inside a fragment instance that declared those arguments.
- Expression-first value contexts may read `state...` only where the surrounding contract allows runtime-state reads.
- Expression-first value contexts may read `step...` only where the surrounding contract allows execution-local step-result reads.
- Expression-first value contexts may depend on read-only probe observation when the surrounding contract allows non-effectful external observation.
- Expression-first value contexts must remain free of connector invocation semantics.
- Expression-first value contexts must remain free of hidden workflow-control semantics.
- Expression-first value contexts should treat plain scalar strings as expressions, quoted strings as explicit string literals, and YAML numeric/boolean/null scalars as ordinary literal values.
- Nested object and list leaves in an expression-first value context must follow the same authored rule recursively.

## Embedded value context

- Embedded value contexts may use local expressions to derive one value for a surrounding field.
- Embedded value contexts may read `inputs...`.
- Embedded value contexts may read `args...` when evaluated inside a fragment instance that declared those arguments.
- Embedded value contexts may read `state...` only where the surrounding contract allows runtime-state reads.
- Embedded value contexts may read `step...` only where the surrounding contract allows execution-local step-result reads.
- Embedded value contexts may depend on read-only probe observation when the surrounding contract allows non-effectful external observation.
- Embedded value contexts must remain free of connector invocation semantics.
- Embedded value contexts must remain free of hidden workflow-control semantics.
- Presence-check helpers such as `is_missing(...)` or `is_present(...)`, if introduced later, must apply only to approved lookup-style references and approved read-only representation-adapter invocations rather than to arbitrary computed expressions.

## Guard context

- Guard context expresses pre-execution policy conditions.
- Guard context is limited to dependencies known at launch time.
- Guard context must remain compatible with read-only, pre-execution analysis.
- Guard context may use workflow-visible inputs and other roots that are safe and meaningful before effectful business steps run.
- Guard context may use pure built-ins and read-only representation-adapter projections when those constructs remain launch-time-safe and pre-execution-safe.
- Guard context must not use representation-adapter write paths such as `->...`.
- Guard context must not depend on `step...`.
- Guard context must not require action execution in order to determine whether execution may proceed.
- Guard context must evaluate to a boolean result; a successful non-boolean result is a guard error rather than an implicit truthiness rule.
- Guard context should keep routine execution policy visible in the workflow declaration rather than encoding that policy in many bespoke probe names.
- Object-form guard items using `uses` may remain available for compatibility, but they should not displace native guard expressions as the preferred stable guard surface.

## Step-condition context

- Step-condition context expresses step-local conditional execution.
- Step-condition context may depend on prior execution-local registered step results when those results already exist before the conditional step is considered.
- Step-condition context may depend on read-only probe observation when the surrounding contract allows non-effectful external observation.
- Step-condition context must remain workflow-owned condition evaluation rather than a hidden branching language.
- Native bare `if` conditions are the preferred step-condition surface.
- Embedded `if: ${...}` remains supported only as a deprecated compatibility form.
- Presence-check helpers such as `is_missing(...)` or `is_present(...)`, if introduced later, must apply only to approved lookup-style references and approved read-only representation-adapter invocations rather than to arbitrary computed expressions.

## Presence-check argument boundary

- A presence-check helper, if introduced, must accept only lookup-style references whose missingness semantics are well-defined and read-only representation-adapter invocations whose absence semantics are contractually tied to adapter `not_found`.
- Allowed argument forms should be listed explicitly rather than inferred from broad expression permissiveness.
- Arbitrary computed expressions, built-in calls, pipelines, boolean compositions, probe calls, and literals must not be treated as valid presence-check arguments.
- A read-only representation-adapter invocation used as a presence-check argument should evaluate to presence success when the invocation succeeds and to absence when it fails specifically with adapter `not_found`.
- Other adapter failures such as `ambiguous`, `invalid_path`, `invalid_root_value`, or `invalid_action` must remain ordinary failures rather than being collapsed into boolean absence.
- A write-path representation-adapter invocation must not be accepted as a presence-check argument.
- Presence checks must preserve the distinction between an explicit `null` value and a missing lookup when the surrounding contract distinguishes them.

## Include-binding context

- Include-binding context evaluates caller-scoped bindings for included fragment arguments.
- Include-binding context may read caller-local roots that are valid at the include site.
- Include-binding context must preserve the distinction between caller scope and fragment-local `args...` scope.
- Include bindings must not implicitly grant the fragment body direct caller-local `step...` scope.
- The preferred authored form for include-site `with` bindings should follow the expression-first value rule rather than requiring `${...}`.

## Whole-tree rule

- Context restrictions apply to the entire local-expression tree.
- A forbidden dependency class must remain forbidden even when nested inside a call argument, list item, comparison, or other subexpression.

## Native versus embedded surfaces

- A native condition context may expose expressions without an interpolation envelope.
- An expression-first value context may expose plain scalar expressions while still preserving explicit quoted string literals.
- An embedded value context may use a distinct authored embedding form for local expressions as an explicit escape surface when the expression is not viable as a YAML plain scalar.
- Surface differences must not erase the underlying context restrictions that determine which roots and dependencies are allowed.
