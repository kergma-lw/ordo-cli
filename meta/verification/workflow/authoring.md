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
- If a future bounded `for_each` is added on `run`, authoring verification should preserve a short explainable distinction between named repeated fragment invocation and inline short repeated `steps` body without treating them as unrelated looping dialects.
- Authoring verification should reject nested `for_each` and nested repeated-body `guards` early enough that agents and humans do not need implementation reading to predict invalidity.
- Workflow-level `let` should help reduce repeated expression noise without hiding whether a workflow is reading inputs, runtime state, step-local data, or read-only observations.
- Validation and diagnostics should keep `let` errors attributable both to the binding declaration and to the authored use site when that distinction matters.
- A valid declaration is not treated as fully sufficient when it is opaque, shell-heavy, or difficult to review.
- When effectful actions publish advisory preflight-observation templates, authoring diagnostics should be able to surface those templates back in workflow-shaped expressions.
- If those rendered recommendations become awkward or long, that is an authoring signal to name important values earlier rather than a reason to hide workflow structure from diagnostics.
- Authoring diagnostics may reuse the same shared context-aware analysis tree as runtime preflight, so long as authoring findings remain distinct from executability blockers.
- The shared analysis tree should preserve enough structural evidence for later `plan`, `explain`, and `next` work rather than discarding it after the first `review` or `check` projection.
