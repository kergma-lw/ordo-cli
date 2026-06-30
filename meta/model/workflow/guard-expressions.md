# Guard expression model

## Concept

A guard expression is a boolean predicate evaluated during the guard phase.

It is modeled as policy over public probe results rather than as a general embedded program.

## Allowed semantic elements

- boolean literals and other JSON-shaped literals suitable for comparison;
- references to workflow inputs such as `inputs.issue`;
- zero-argument public probe references;
- parameterized public probe references;
- documented field access over probe outputs;
- boolean composition;
- comparison operators.

## Probe reference semantics

- A plain string item in `guards` denotes a compact guard expression.
- A zero-argument probe reference may appear without empty call syntax.
- A parameterized probe reference carries explicit named arguments in the preferred authoring form.
- Within one guard expression, repeated identical probe references should be evaluated once and reused.
- A probe reference inside an expression must resolve against the same public probe contract surface used by explicit operation-form guards.
- A public probe surface used by expressions should remain as orthogonal as practical rather than encoding many bespoke policy predicates in probe names.
- A new probe should not be introduced merely to avoid a short comparison, boolean composition, or small membership check over existing probe outputs.

## Output access semantics

- Field access after a probe reference means reading documented structured output from that probe result.
- Field access is not a general object method system.
- Public contract documentation must define which output fields are stable enough to reference from guard expressions.
- A boolean-valued field may be used directly as a condition.
- Non-boolean probe outputs should be compared through explicit documented field access such as `git.branch.value`.

## Guard list semantics

- A workflow may contain multiple guard items.
- Each guard item yields a boolean pass/fail outcome or an evaluation failure.
- Multiple guard items combine as an ordered conjunction over the guard list.

## Failure semantics

- A false comparison result means the guard blocks execution.
- A probe evaluation failure inside an expression is not the same thing as a false comparison result.
- Guard explanation should preserve both the boolean structure and the probe-level outcome details.
- Guard evaluation must remain side-effect free.
- A statically invalid field path should fail before runtime guard evaluation begins.
