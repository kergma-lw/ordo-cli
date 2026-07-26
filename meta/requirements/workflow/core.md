# Workflow requirements

## Authoring and shape

- A workflow file must be writable by both humans and agents.
- Workflow authoring from existing public operations is a primary product path rather than a niche expert path.
- Validation must fail on unknown fields in stable workflow schema.
- A human reviewer must be able to locate policy and guardrails in the declaration itself rather than reconstructing them from implementation code alone.
- An agent author must be able to predict whether a workflow is valid, resolvable, and likely executable from schema, examples, and connector contracts.
- The contract must minimize hidden shell semantics that change workflow meaning without explicit declaration.
- The default authoring path should favor composition of existing operations and profiles over creation of new connector semantics.
- Explicit workflow-owned data flow between prior and later steps should be representable without inventing connector-local storage hacks.
- A workflow may declare workflow-local named expressions through a top-level `let` surface when that keeps long local expressions readable.
- Reusable workflow fragments should support explicit local argument contracts.
- Explicit fragment argument contracts must not by themselves force static composition and runtime-scoped invocation to collapse into one reuse primitive when their semantics diverge materially.
- If the product later introduces both `include` and `run`, the distinction must remain brief enough for humans and agents to predict from contract docs and examples.
- All user-facing activation inputs must be declared in the root workflow `inputs` contract even when they are consumed only inside included fragments or reusable run targets.
- Validation after workflow assembly must reject any `inputs.<name>` reference that does not resolve to a root-declared workflow input.
- A successful workflow run may accumulate one or more authored workflow-local return values through explicit `result` steps.
- Workflow-local result values must accumulate in execution order rather than replacing prior result values for that workflow run.
- A successful workflow run may also publish one or more authored global output values through explicit `publish` steps.
- Published global output values must accumulate in execution order across the enclosing run session rather than replacing prior published values.
- A `run` step may declare `register` when the product chooses to expose the just-completed callee workflow-local `results` list back to the caller.
- If the product later introduces `for_each` on `run`, that surface must be bounded to array-valued sources rather than to adapter-specific iterable protocols.
- If `run` later supports `for_each`, the step-level `if` condition must still apply to the whole declared step rather than becoming one per-item filter surface.
- If `run` later supports `for_each`, lexical nesting of `for_each` inside another `for_each` in the same authoring surface must remain invalid.
- If `run` later supports both `for_each` and `register`, the registered value should preserve one array of per-run workflow-local result payloads rather than flattening all returned values into one undifferentiated list.
- If the product later emits a synthetic fallback result for successful runs without explicit results, that fallback must apply only to the requested top-level workflow run rather than to internal include, `pre_run`, or nested `run` boundaries.
- Workflow input declarations may carry one optional author-provided `hint` string for invocation guidance.
- Input `hint` is guidance only, not a validation rule or runtime-inferred contract fact.

## Product boundary

- Core semantics must stay small and explainable.
- The format must prefer explicit fields over implicit behavior.
- Drift between docs, schema, examples, and runtime must be detectable.
- Workflow and profile authoring must remain easier and more common than connector authoring in early product stages.
