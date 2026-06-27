# Policy guard expressions

## Role

Guard expressions exist to keep execution conditions short, reviewable, and explicit.

They are a policy surface, not a general programming surface.

## Why they exist

Without a compact expression surface, policy tends to drift into one of two bad shapes:

- shell-heavy guard logic that is difficult to review or explain;
- many narrow probe names that encode policy in operation naming rather than in the workflow declaration.

In the long run, guard policy should prefer a minimal and orthogonal public probe surface over a growing catalog of specialized policy probes.

Guard expressions are meant to preserve the original workflow promise:

- state the conditions for execution briefly;
- state the ordered actions that follow if conditions pass.

## Boundary

Guard expressions may:

- invoke public probe operations;
- read documented probe result fields;
- compare values;
- combine boolean conditions.

Guard expressions must not:

- execute effectful actions;
- become a general scripting language;
- hide complex operational semantics that should remain in public connector contracts.

Guard expressions also should not require a bespoke public probe name for every routine boolean policy question.

## Readability standard

A good guard section should usually fit in a short top-to-bottom review window.

If the conditions take a screen of repetitive structured boilerplate, the product is failing one of its core workflow goals even if the shape is technically machine-checkable.

## Open pressure that guard expressions do not settle yet

Guard expressions address compact policy declaration for execution preconditions.

They do not by themselves settle later workflow control-flow questions such as:

- step-level conditional execution;
- registering step results for later use;
- branching based on effectful step outcomes;
- cross-step data flow semantics.

These concerns should remain explicit future design work rather than being smuggled into guard expression semantics.
