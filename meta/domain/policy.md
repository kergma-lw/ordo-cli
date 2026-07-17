# Policy domain

## Guard

A guard is a precondition check evaluated as part of policy before a later effectful step block may run.

A guard is first-class and must not collapse into a hidden step convention.

Detailed runtime expectations for guard coverage, incompleteness, and preflight verdict honesty live in `meta/model/runtime/check-semantics.md`.

## Policy

Policy is the set of constraints that determines whether a workflow may proceed and under which conditions.

In Ordo, policy must be visible and reviewable in workflow and profile structure,
not buried in shell control flow.

## Explainability

`explain` must answer these questions:

- why execution is blocked or allowed;
- which guards passed or failed;
- which steps are executable, skipped, or blocked;
- which next action a human or agent can take.

This is stronger than logs, traces, or raw exception text.
