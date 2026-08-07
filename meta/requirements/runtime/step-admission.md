# Runtime requirements for step admission gates

## Role

- The runtime should support step-level admission control through workflow-authored `gate` conditions.
- A `gate` should protect step execution after prerequisite observations and before the protected step begins running.
- A `gate` should not replace workflow-entry `guards` or step-level conditional `if` semantics.

## Evaluation order

- When a step declares `if`, the runtime must evaluate `if` before any `gate` on the same step.
- If `if` evaluates to `false`, the step must be skipped and the runtime must not evaluate `gate` for that step.
- When a step declares `gate`, the runtime must evaluate `gate` immediately before step execution.
- If `gate` evaluates to `true`, the runtime may execute the step normally.
- If `gate` evaluates to `false`, the runtime must not execute the step and must fail the workflow on that step.

## Admission boundary

- `gate` is step-level admission control after observations, not early workflow blocking.
- `gate` must be able to depend on runtime-derived read-only knowledge that was established by earlier steps.
- `gate` must not depend on outputs of the current step it protects.
- A blocked `gate` must not be rewritten into a silent skip.

## Outcome model

- The runtime should preserve a distinct step outcome for gate blocking such as `gate_failed`.
- A gate-blocked step must remain distinguishable from ordinary execution failure even when both lead to workflow failure.
- A gate-blocked step must not publish normal step outputs or registered results.

## Check semantics

- `check` should perform relevant read-only observations needed to evaluate a reachable `gate` when that can be done without effectful business execution.
- `check` should report whether a gated step can run, cannot run, or cannot yet be established honestly from available knowledge.
- `check` should identify which gate clauses passed, failed, or remain unknown or unobserved.
- `check` must not execute effectful business steps to satisfy a `gate`.

## Explainability

- `run` and `explain` outputs should preserve that a step was blocked by `gate` rather than skipped or generally failed.
- Runtime outputs should preserve the failing gate condition or failing subconditions when available.
- Structured `gate` conditions should remain explainable in terms of their `all`, `any`, and `not` structure.

## Planning and review projections

- `plan` should show read-only observations before a gated step and should preserve that the step executes only if the `gate` passes.
- `review` should distinguish optional-routing `if` usage from readiness or admission `gate` usage.
- `review` should prefer structured `gate` form for multi-clause readiness checks and may flag unreadable long string-form gates as weak authoring shape.
