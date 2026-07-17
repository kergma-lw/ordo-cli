# Local expression contexts

## Embedded value context

Embedded value context models one derived value inside a larger value-bearing field.

Typical surfaces include step inputs, value-bearing workflow fields, include argument bindings, and other scalar positions that reuse local-expression evaluation.

It belongs to the value-oriented context family.

It may consume whatever roots are available at its resolution point, subject to higher-level purity and control-surface exclusions.

## Guard context

Guard context models pre-execution policy evaluation.

Its distinctive property is not a separate expression language, but a restricted dependency model:

- the expression must be meaningful from launch-time-known dependencies before effectful business steps run;
- execution-local `step...` dependencies are excluded;
- the result participates in execution admission rather than in post-step branching.

It belongs to the condition-oriented context family.

## Step-condition context

Step-condition context models conditional execution of one workflow step.

Unlike guard context, it may legitimately depend on prior execution-local registered results because it is evaluated after earlier steps may already have run.

It also belongs to the condition-oriented context family.

## Include-binding context

Include-binding context models caller-side argument preparation for included fragments.

The include site may evaluate caller-scoped local expressions before the expanded fragment body receives fragment-local `args...` bindings.

That caller-side evaluation does not make included fragment bodies owners of caller-local `step...` scope.

It belongs to the value-oriented context family.

It may consume whatever caller-scoped roots are available at the include site.

## Native and embedded authored forms

The model allows both:

- native expression contexts whose primary meaning is already conditional or predicate-oriented;
- embedded expression contexts whose expressions appear inside a broader value-bearing field.

This distinction is about authored surface, not about separate semantic languages.

## Tree-scoped restrictions

Context policy governs the whole parsed expression tree.

A context therefore validates dependency classes structurally rather than only checking the root node.
