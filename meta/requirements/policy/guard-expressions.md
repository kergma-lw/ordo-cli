# Policy requirements for guard expressions

## Purpose

- Guard policy should be expressible in workflow declarations without requiring a bespoke named probe for every common predicate.
- Policy must remain visible in the workflow rather than being recoverable only from probe implementation details or probe naming conventions.

## Expression scope

- Guard expressions may evaluate only public `probe` operations.
- Guard expressions may compare probe outputs and combine boolean conditions.
- Guard expressions must not call `action` operations.
- Guard expressions must not require a general-purpose expression language with arbitrary functions or user-defined evaluation semantics.

## List semantics

- Each item in `guards` is a separate boolean guard clause.
- The `guards` list combines with implicit `and` semantics across items.
- `or` semantics should be expressed inside one guard expression rather than by overloading list structure.

## Minimum boolean support

- The policy surface should support at least `and`, `or`, `not`, and parentheses for grouping within a single guard expression.
- The policy surface should support at least `==`, `!=`, `in`, and `not in` comparisons needed for common operational predicates.
- Boolean-valued probe facts may appear directly as conditions without an explicit equality comparison.

## Explainability

- Runtime results for failed guard expressions must identify which subcondition evaluated to false or failed to evaluate.
- When a probe inside a guard expression fails operationally, the runtime must preserve the distinction between "condition evaluated false" and "probe could not be evaluated safely".
- Runtime results should preserve a machine-usable evaluation trace rather than only the final blocked guard identity.
