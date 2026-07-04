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

## Probe versus policy boundary

As a default design rule, probes should expose stable observable facts and guard expressions should compose those facts into policy.

This means a proposed new probe is a poor fit when its only purpose is to avoid writing a short expression such as:

- a boolean conjunction or disjunction;
- a direct equality or inequality comparison;
- a small membership check over documented probe outputs.

A proposed new probe is a better fit when guard composition would otherwise:

- repeat awkward normalization across many workflows;
- require expression-language growth beyond compact reviewable policy;
- expose unstable operational detail that belongs inside the connector contract.

Probe naming should therefore prefer observable facts over local verdicts.

For example, names such as `git.branch`, `git.worktree`, or `gh.issue` fit this boundary better than names that directly encode policy intent such as `git.branch_not_main` or `gh.issue_ready_for_review`.

## Readability standard

A good guard section should usually fit in a short top-to-bottom review window.

If the conditions take a screen of repetitive structured boilerplate, the product is failing one of its core workflow goals even if the shape is technically machine-checkable.

## Boundary pressure that guard expressions do not settle by themselves

Guard expressions address compact policy declaration for execution preconditions.

They do not by themselves settle later workflow control-flow questions such as:

- step-level conditional execution;
- branching based on effectful step outcomes;
- cross-step data flow semantics.

These concerns should remain explicit separate workflow surfaces rather than being smuggled into guard expression semantics.
