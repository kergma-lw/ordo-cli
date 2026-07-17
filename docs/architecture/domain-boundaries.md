# Domain boundaries

## In scope

- local operational workflows
- public connector contracts
- validation and explainability
- human + agent authored declarations
- composition via playbooks, profiles, and explicit local extensions

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

## Architectural boundary themes

At the architecture level, Ordo keeps several boundary themes visible:

- workflow declarations hold orchestration intent rather than implementation-heavy transformation logic;
- playbooks hold project-local launch and resolution context rather than workflow business-step logic;
- connectors act as a public integration library layer rather than as private runtime internals;
- runtime and policy surfaces preserve distinctions between blocked, planned, failed, and successful execution states.

The operational source-of-truth rules for these themes live in the corresponding `meta/domain/*` documents rather than in this architecture overview.

## Related runtime and domain docs

- `meta/domain/playbook.md`
- `meta/domain/connector.md`
- `meta/domain/local-expressions.md`
- `meta/domain/workflow.md`
- `meta/domain/runtime.md`
- `meta/domain/policy.md`
