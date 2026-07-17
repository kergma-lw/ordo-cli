# Local expression context requirements

## Embedded value context

- Embedded value contexts may use local expressions to derive one value for a surrounding field.
- Embedded value contexts may read `inputs...`.
- Embedded value contexts may read `args...` when evaluated inside a fragment instance that declared those arguments.
- Embedded value contexts may read `state...` only where the surrounding contract allows runtime-state reads.
- Embedded value contexts may read `step...` only where the surrounding contract allows execution-local step-result reads.
- Embedded value contexts must remain free of connector invocation semantics.
- Embedded value contexts must remain free of hidden workflow-control semantics.

## Guard context

- Guard context expresses pre-execution policy conditions.
- Guard context is limited to dependencies known at launch time.
- Guard context must remain compatible with read-only, pre-execution analysis.
- Guard context may use workflow-visible inputs and other roots that are safe and meaningful before effectful business steps run.
- Guard context must not depend on `step...`.
- Guard context must not require action execution in order to determine whether execution may proceed.
- Guard context should keep routine execution policy visible in the workflow declaration rather than encoding that policy in many bespoke probe names.
- Object-form guard items using `uses` may remain available for compatibility, but they should not displace native guard expressions as the preferred stable guard surface.

## Step-condition context

- Step-condition context expresses step-local conditional execution.
- Step-condition context may depend on prior execution-local registered step results when those results already exist before the conditional step is considered.
- Step-condition context must remain workflow-owned condition evaluation rather than a hidden branching language.
- Native bare `if` conditions are the preferred step-condition surface.
- Embedded `if: ${...}` remains supported only as a deprecated compatibility form.

## Include-binding context

- Include-binding context evaluates caller-scoped bindings for included fragment arguments.
- Include-binding context may read caller-local roots that are valid at the include site.
- Include-binding context must preserve the distinction between caller scope and fragment-local `args...` scope.
- Include bindings must not implicitly grant the fragment body direct caller-local `step...` scope.

## Whole-tree rule

- Context restrictions apply to the entire local-expression tree.
- A forbidden dependency class must remain forbidden even when nested inside a call argument, list item, comparison, or other subexpression.

## Native versus embedded surfaces

- A native condition context may expose expressions without an interpolation envelope.
- An embedded value context may use a distinct authored embedding form for local expressions.
- Surface differences must not erase the underlying context restrictions that determine which roots and dependencies are allowed.
