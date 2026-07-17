# Workflow requirements for step conditions

## Role

- The workflow authoring surface should support optional step-level eligibility conditions through an `if` field.
- Step conditions should allow one declared workflow step to execute or be skipped without introducing first-class branch blocks, loops, or join semantics.
- Step conditions should reuse the existing value-expression surface rather than introducing a third workflow expression language.

## Authoring shape

- Any workflow step form may declare an optional `if` field.
- The preferred `if` field should use a native bare step-condition expression.
- The older embedded form `if: ${...}` may remain supported as deprecated compatibility surface.
- YAML-native boolean literals are not part of this MVP `if` surface.

## Expression boundary

- An `if` expression may read `inputs...` values.
- An `if` expression may read `state...` values.
- An `if` expression may read prior registered `step...` results.
- An `if` expression must never read future step results.
- An `if` expression must never call connector operations or probes.
- An `if` expression must never perform conditional value selection through ternary syntax, `if(...)`, `select(...)`, `case(...)`, or equivalent forms.

## Boolean discipline

- An `if` expression must evaluate to a boolean result.
- Step conditions should support boolean composition through `and`, `or`, `not`, and parentheses.
- Boolean composition in step conditions should combine only boolean-valued subexpressions.
- A direct reference is valid in `if` only when the referenced value is boolean.
- Predicate transforms such as equality comparison may be used when they return boolean.
- `not` should accept only boolean input and return boolean output.
- Existing value-expression pipelines may appear inside boolean subexpressions when they produce boolean output.
- Shared boolean syntax with guards should not change the allowed step-condition reference domains or permit probe calls.
- Failure to evaluate an `if` expression must fail execution rather than being treated as `false`.

## Register interaction

- A workflow step must not declare both `if` and `register` in the MVP.
- The MVP should avoid publishing registered results for skipped steps.

## Runtime behavior

- If a step condition evaluates to `true`, the step executes normally.
- If a step condition evaluates to `false`, the step is intentionally skipped.
- A skipped step must remain distinguishable from guard blocking, validation failure, resolution failure, and execution failure.
- The runtime should preserve machine-usable information that a step was skipped because its condition evaluated to `false`.

## Explainability

- `plan` should preserve that a step is conditional when an `if` field is present.
- `explain` and `execute` outputs should preserve whether a conditional step executed, was skipped because its condition evaluated to `false`, or failed because its condition could not be evaluated.
