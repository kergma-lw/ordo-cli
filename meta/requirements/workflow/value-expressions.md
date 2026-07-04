# Workflow requirements for value expressions

## Role

- Workflows may use value expressions for pure local computation of derived values.
- Value expressions exist to keep common normalization and formatting inside workflow authoring without pushing those concerns into connector operations.
- Value expressions are part of workflow authoring surface, not a second orchestration or integration language.

## Allowed capability

- A value expression may read declared workflow inputs.
- A value expression may read runtime state through the documented `state...` read surface.
- A value expression may read prior registered step results through the documented `step...` read surface.
- A value expression may combine multiple local values into one derived value.
- A value expression may apply a closed set of deterministic built-in transforms.
- Inline composition should use the pipe form `|` as the canonical compact authoring surface.
- String formatting may be expressed as a root built-in form.

## Permanent exclusions

- A value expression must never cause side effects.
- A value expression must never call connector operations, whether action or probe.
- A value expression must never read future step results.
- A value expression must never encode workflow control flow such as branching, looping, or step selection.
- A value expression must never duplicate guard or policy semantics as a general boolean language.
- A value expression must never support user-defined functions, macros, operators, or workflow-defined extension hooks.
- A value expression must never become an open-ended collection programming or query language.
- A value expression must never rely on project-defined syntax whose meaning is not part of the stable product contract.

## Readability and reviewability

- Inline value expressions should stay short enough for quick review inside workflow fields.
- Built-in transforms should be understandable left-to-right without reconstructing hidden evaluation rules.
- Validation and diagnostics should identify the failing segment of a value expression rather than only reporting a generic value-resolution failure.

## YAML alternative policy

- Some root built-in value forms may also provide a structured YAML equivalent when inline syntax becomes hard to read.
- YAML equivalence is selective rather than universal.
- Not every inline value expression needs or should have a YAML equivalent.
- A YAML equivalent, when present, should represent the same semantic operation as its inline root form rather than introducing a parallel computation model.

## Growth discipline

- Product growth should prefer adding a small number of high-value built-in transforms over widening value expressions into a general programming language.
- New value-expression capability is a poor fit when it would be better modeled as workflow control, guard policy, connector behavior, or runtime-owned state mutation.
- New value-expression capability is also a poor fit when it would require open-ended semantics for iteration, branching, remote access, or user-defined evaluation.
