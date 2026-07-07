# Workflow authoring verification

## Rule

Workflow and profile authoring must remain a first-class and agent-usable surface.

## Checks

- Public operations are discoverable enough for composition without reading connector implementation internals.
- Schema, examples, and runtime diagnostics are sufficient for iterative repair of an authored workflow.
- Routine project adaptation prefers composing workflows and profiles over introducing new connector semantics.
- Reusable included fragments remain understandable as one author-facing `include` surface even when they declare fragment-local `args`.
- A valid declaration is not treated as fully sufficient when it is opaque, shell-heavy, or difficult to review.
