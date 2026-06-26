# Domain boundaries

## In scope

- local operational workflows
- public connector contracts
- validation and explainability
- human + agent authored declarations
- composition via profiles and explicit local extensions

## Product identity boundary

Ordo is not just a YAML task runner.

The intended center of gravity is:

- guarded workflow evaluation;
- explainable runtime decisions;
- stable public connector/operation contracts;
- structured results for both humans and agents.

The project only remains meaningfully distinct if these stay first-class in runtime behavior,
not just in documentation language.

## Nearby tool boundary

Tools such as shell helpers, task runners, and pipeline engines are relevant references,
but they are not the target identity.

Useful contrast:

- task runner / pipeline engine: primarily answers **what steps should run**;
- Ordo: must also answer **whether execution is allowed, why, and what would happen before effectful execution starts**.

This means Ordo should remain analysis-first rather than execution-first.

For the core contract, this also means:

- agent-usable decision support is a primary surface, not a side effect of logs;
- `check` / `plan` / `explain` are part of the runtime contract, not optional convenience commands;
- blocked-before-execution remains a first-class outcome category.

## Fixed connector domains for v0

- `git`
- `gh`
- `shell`

## Out of scope for the core

- distributed workflow coordination
- infra inventory management as a primary model
- opaque shell-first orchestration
- giant built-in standard library from day one
- generic "just another pipeline DSL" positioning

## Explicit non-identity

Ordo should not collapse into any of the following:

- a YAML wrapper around shell scripts;
- a step runner whose only meaningful output is logs and exit code;
- a system where `explain` means little more than replaying errors after failure;
- a loose module namespace without stable public operation semantics.
- a runtime whose primary value is execution while decision support is reconstructed externally.

If these become the dominant shape, the project drifts toward existing task runners and loses its reason to exist.

## Boundary rule

Workflow files hold orchestration intent.
Algorithmic transformation lives in connector operation implementation code.

## Execution rule

Policy evaluation belongs in explicit guards and runtime modes.
Connector code may implement checks, but the workflow/runtime contract must preserve the distinction between:

- blocked before execution;
- planned but not executed;
- executed and failed;
- executed and succeeded.

## Related domain docs

- connector semantics: `domain/connector.md`
- workflow semantics: `domain/workflow.md`
- runtime semantics: `domain/runtime.md`
- policy semantics: `domain/policy.md`
