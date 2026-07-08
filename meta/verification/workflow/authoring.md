# Workflow authoring verification

## Rule

Workflow and profile authoring must remain a first-class and agent-usable surface.

## Checks

- Public operations are discoverable enough for composition without reading connector implementation internals.
- Schema, examples, and runtime diagnostics are sufficient for iterative repair of an authored workflow.
- Routine project adaptation prefers composing workflows and profiles over introducing new connector semantics.
- Reusable included fragments remain understandable as a static-composition `include` surface even when they declare fragment-local `args`.
- Authoring verification should not require all reusable-fragment semantics to collapse into `include` when a later runtime-scoped invocation surface would be clearer.
- If a future `run` surface is introduced, authoring verification should preserve a short explainable distinction between static composition and runtime-scoped fragment invocation.
- A valid declaration is not treated as fully sufficient when it is opaque, shell-heavy, or difficult to review.
