# Agent authoring verification report

## Scope

This report captures the current status of issue #16 against the repository state available in this work.

It evaluates whether a sufficiently capable agent can author and repair workflows and profiles from the public contract surface alone, without relying on connector implementation internals.

## Method

- Review the published contract surface in `meta/packs/core.md`.
- Review author-facing docs in `docs/`, `schema/`, `connectors/`, and `examples/`.
- Check whether examples stay inside the documented v0 connector boundary.
- Check whether the repository already exposes enough structured diagnostics to support iterative repair.

## Findings

### Discoverability

Partial pass.

The public surface already makes several important facts discoverable:

- the v0 connector families are `git`, `gh`, and `shell`;
- workflows are built from `guards` and ordered `steps`;
- authoring is intended to be composition-first rather than connector-first.

However, discoverability is still incomplete because the repository does not yet publish a canonical operation inventory with per-operation input and result contracts.

### Composition-first authoring

Partial pass.

The examples demonstrate that non-trivial workflows can be expressed by composing public operations.

During this verification pass, the examples were corrected to stay inside the published v0 connector boundary:

- `github.*` references were aligned to `gh.*`;
- `run.profile` was removed from a v0 example because `run` is documented only as a possible future connector domain.

This removes immediate drift between the examples and the documented contract surface, but it does not yet prove that the published operation set is sufficient for routine customization across real projects.

### Iterative repair via structured feedback

Fail for now.

The meta contract requires machine-usable validation, resolution, planning, and explanation surfaces. The current repository snapshot still exposes only the schema, examples, and design docs. It does not yet expose implemented structured diagnostics for:

- validation failure;
- resolution failure;
- likely executability;
- explanation and next safe action.

An agent can infer intent from the docs, but cannot yet repair authored workflows through stable runtime feedback alone.

### Profiles

Not yet proven.

The meta contract discusses profile composition and explicit overrides, but the current repository snapshot does not yet provide a concrete public profile contract and runtime verification path strong enough to demonstrate agent-usable profile repair.

## Remaining gaps against meta truth

Before issue #16 can be considered fully satisfied, the repository still needs at least:

- a canonical public operation registry or equivalent contract index;
- implemented structured outputs for `check`, `plan`, `execute`, and `explain`;
- explicit public profile contract examples and validation behavior;
- scenario-style verification that an authored workflow can be repaired from structured diagnostics without log scraping.

## Current conclusion

The repository now better respects the documented v0 boundary at the example level, so it is less likely to drift silently from the meta packs.

But issue #16 is still only partially satisfied in the current snapshot. The public authoring story is directionally coherent, yet the runtime and diagnostics needed for full agent-authorable verification are not implemented here yet.
