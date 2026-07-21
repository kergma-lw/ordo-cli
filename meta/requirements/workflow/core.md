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
- Reusable workflow fragments should support explicit local argument contracts.
- Explicit fragment argument contracts must not by themselves force static composition and runtime-scoped invocation to collapse into one reuse primitive when their semantics diverge materially.
- If the product later introduces both `include` and `run`, the distinction must remain brief enough for humans and agents to predict from contract docs and examples.
- All user-facing activation inputs must be declared in the root workflow `inputs` contract even when they are consumed only inside included fragments or reusable run targets.
- Validation after workflow assembly must reject any `inputs.<name>` reference that does not resolve to a root-declared workflow input.
- A successful workflow run may publish one or more authored result values through existing `result` steps without changing the `result` step syntax.
- Published result values must accumulate in execution order rather than replacing prior published results.
- If the product later emits a synthetic fallback result for successful runs without explicit results, that fallback must apply only to the requested top-level workflow run rather than to internal include, `pre_run`, or nested `run` boundaries.
- Workflow input declarations may carry one optional author-provided `hint` string for invocation guidance.
- Input `hint` is guidance only, not a validation rule or runtime-inferred contract fact.

## Product boundary

- Core semantics must stay small and explainable.
- The format must prefer explicit fields over implicit behavior.
- Drift between docs, schema, examples, and runtime must be detectable.
- Workflow and profile authoring must remain easier and more common than connector authoring in early product stages.
