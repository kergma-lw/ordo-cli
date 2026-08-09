# Workflow requirements for step conditions

## Role

- The workflow authoring surface should support optional step-level eligibility conditions through an `if` field.
- The workflow authoring surface should support optional step-level admission conditions through a `gate` field.
- Step conditions should allow one declared workflow step to execute or be skipped without introducing first-class branch blocks, loops, or join semantics.
- Step admission conditions should allow one declared workflow step to be blocked with meaningful failure after prerequisite read-only observations have been established.
- Step conditions should reuse the common local-expression system rather than introducing a third workflow expression language.

## Authoring shape

- Any workflow step form may declare an optional `if` field.
- Any workflow step form may declare an optional `gate` field.
- The preferred `if` field may use either a native bare step-condition expression or a native structured condition form.
- The preferred `gate` field may use either a native bare step-condition expression or a native structured condition form.
- String-expression and structured-condition `if` forms are equal-authority authoring surfaces.
- String-expression and structured-condition `gate` forms are equal-authority authoring surfaces.
- A list-form `if` value must be interpreted as an implicit `all` condition whose items are evaluated in order.
- A list-form `gate` value must be interpreted as an implicit `all` condition whose items are evaluated in order.
- An object-form `if` value may express explicit boolean composition through `all`, `any`, or `not`.
- An object-form `gate` value may express explicit boolean composition through `all`, `any`, or `not`.
- Structured condition items may nest other structured condition nodes.
- Structured `gate` items may nest other structured condition nodes.
- The older embedded form `if: ${...}` may remain supported as deprecated compatibility surface.
- The older embedded form `gate: ${...}` may remain supported as deprecated compatibility surface.
- YAML-native boolean literals are not part of this MVP `if` surface.
- YAML-native boolean literals are not part of this MVP `gate` surface.

## Expression boundary

- An `if` expression may read `inputs...` values.
- An `if` expression may read `state...` values.
- An `if` expression may read prior registered `step...` results.
- An `if` expression may depend on approved read-only probe observation when the surrounding step-condition context allows non-effectful external observation.
- An `if` expression must never read future step results.
- Structural nesting alone must not change the approved step-condition dependency classes for one otherwise equivalent `if` surface.
- An `if` expression must never trigger effectful connector execution.
- An `if` expression must never perform conditional value selection through ternary syntax, `if(...)`, `select(...)`, `case(...)`, or equivalent forms.
- A `gate` expression may read `inputs...` values.
- A `gate` expression may read `state...` values.
- A `gate` expression may read prior registered `step...` results.
- A `gate` expression may depend on approved read-only probe observation when the surrounding step-condition context allows non-effectful external observation.
- A `gate` expression must never read future step results.
- A `gate` expression must never read outputs of the current step it protects.
- Structural nesting alone must not change the approved step-condition dependency classes for one otherwise equivalent `gate` surface.
- A `gate` expression must never trigger effectful connector execution.
- A `gate` expression must never perform conditional value selection through ternary syntax, `if(...)`, `select(...)`, `case(...)`, or equivalent forms.

## Boolean discipline

- An `if` expression must evaluate to a boolean result.
- A structured `if` condition must evaluate to a boolean result under the same step-condition context rules as an expression-form `if`.
- A `gate` expression must evaluate to a boolean result.
- A structured `gate` condition must evaluate to a boolean result under the same step-condition context rules as an expression-form `gate`.
- Step conditions should support boolean composition through `and`, `or`, `not`, and parentheses.
- Step conditions should also support boolean composition through structured `all`, `any`, and `not` condition nodes.
- Boolean composition in step conditions should combine only boolean-valued subexpressions.
- Structured boolean composition should combine only boolean-valued child conditions.
- A direct reference is valid in `if` only when the referenced value is boolean.
- A direct reference is valid in `gate` only when the referenced value is boolean.
- Predicate transforms such as equality comparison may be used when they return boolean.
- `not` should accept only boolean input and return boolean output.
- Structured `not` should accept exactly one boolean-valued child condition and return boolean output.
- Existing embedded-value pipelines may appear inside boolean subexpressions when they produce boolean output.
- Shared boolean syntax with guards should not change the allowed step-condition reference domains or permit probe calls.
- Failure to evaluate an `if` expression must fail execution rather than being treated as `false`.
- Failure to evaluate any structured `if` condition node must fail execution rather than being treated as `false`.
- Failure to evaluate a `gate` expression must fail execution rather than being treated as `false`.
- Failure to evaluate any structured `gate` condition node must fail execution rather than being treated as `false`.

## Register interaction

- A workflow step must not declare both `if` and `register` in the MVP.
- The MVP should avoid publishing registered results for skipped steps.
- A workflow step must not declare both `gate` and `register`.
- A standalone step-local `gate` checkpoint step may omit a step body form and should act only as one admission boundary.

## Runtime behavior

- If a step condition evaluates to `true`, the step executes normally.
- If a step condition evaluates to `false`, the step is intentionally skipped.
- If a step-level admission condition evaluates to `true`, the step remains eligible to execute.
- If a step-level admission condition evaluates to `false`, the step must not execute and the workflow must fail on that step.
- A skipped step must remain distinguishable from guard blocking, validation failure, resolution failure, and execution failure.
- A gate-blocked step must remain distinguishable from guard blocking, skip, validation failure, resolution failure, and execution failure.
- The runtime should preserve machine-usable information that a step was skipped because its condition evaluated to `false`.
- The runtime should preserve machine-usable information that a step was blocked because its `gate` condition evaluated to `false`.
- When a step declares both `if` and `gate`, runtime must evaluate `if` first and must not evaluate `gate` for a skipped step.

## Explainability

- `plan` should preserve that a step is conditional when an `if` field is present.
- `explain` and `execute` outputs should preserve whether a conditional step executed, was skipped because its condition evaluated to `false`, or failed because its condition could not be evaluated.
- `plan` should preserve that a step is admission-gated when a `gate` field is present.
- `check` should evaluate admission conditions from read-only available knowledge when possible and should report whether the gated step can run, cannot run, or cannot yet be established honestly.
- `explain` and `execute` outputs should preserve whether a gated step executed, was blocked because its condition evaluated to `false`, or failed because its condition could not be evaluated.
