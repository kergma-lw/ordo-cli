# ADR 0005: local expressions use one context-governed family

## Status

Accepted.

## Context

The project had drifted toward separate guard-expression and value-expression axes in both docs and runtime implementation.

That split obscured the intended semantic model:

- expressions are one workflow-owned local surface;
- different workflow fields impose different timing and dependency restrictions;
- those restrictions belong to expression contexts, not to unrelated per-surface languages.

## Decision

Treat local expressions as one product-owned family with explicit contexts.

The initial contexts are:

- guard context;
- step-condition context;
- embedded value context;
- include-binding context.

The initial roots are:

- `inputs...`;
- `args...`;
- `state...`;
- `step...`.

Context restrictions apply to the entire expression tree, not only to the root term.

### Guard context

Guard context is limited to dependencies known at launch time.

This means guard context may use:

- `inputs...`;
- fragment-local `args...` when present;
- `state...`;
- guard-safe pre-execution evaluation surfaces.

Guard context must not depend on `step...` anywhere in the expression tree.

### Step-condition context

Step-condition context may depend on whatever is available when the step condition is evaluated, including prior execution-local `step...` results.

### Include-binding context

Include-binding context evaluates caller-scoped bindings at the include boundary.

It may depend on whatever is available at the include site, including caller-local `step...` results.

The included fragment body does not thereby gain direct caller-local step scope; it receives only the already-bound values.

### Embedded value context

Embedded value context may depend on whatever is available at the point of value resolution.

It remains a pure local-expression surface and must not become effectful execution or hidden workflow control.

## Consequences

- documentation should be organized around `local-expressions` rather than separate guard-expression and value-expression domain axes;
- runtime implementation should converge toward a shared local-expression core with explicit context policy;
- syntax and authored-surface differences may remain, but they must not redefine the conceptual model into unrelated expression systems.
