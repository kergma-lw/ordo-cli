# Connector domain

## What a connector is

A connector is a public integration contract family that a workflow relies on.

## What a connector owns

Connector owns:
- namespace;
- shared bootstrap;
- family-level prerequisites;
- shared runtime context;
- operation registry.

## What an operation is

An operation is a concrete public operation within a connector family.

For connector operations, it is important to distinguish at least two operation kinds:
- `probe` — observes the world and returns structured observations without intended side effects;
- `action` — performs an effectful operation and returns a structured summary of its effects.

An operation contract must define:
- inputs;
- prerequisites;
- effects;
- outputs;
- failure modes.

## Explainability and result discipline

Every connector operation must:
- return a structured result both on success and on failure;
- be able to explain its outcome locally within its narrow semantic domain;
- preserve the result contract even under an internal exception.

Connector operations should remain small, local, and readable authoring units.
They should expose narrow integration semantics rather than absorb runtime orchestration behavior.

Implications:
- a `probe` must return not only an outcome but also meaningful observations and diagnostics;
- an `action` must return not only an outcome but also an effect summary and diagnostics;
- raw stdout/stderr, when produced by an operation, are supplementary detail fields rather than the basis of the contract.

## Mode-agnostic operation authoring

Connector operations should be authored as mode-agnostic integration units.
They should not directly encode `check`, `plan`, `explain`, or `next` behavior.

Instead, each operation should expose a structured local surface rich enough for runtime to derive those behaviors.

Implications:
- probes should return stable observations rather than policy-shaped orchestration decisions;
- actions should return stable effect summaries rather than mode-specific execution narratives;
- operation code should stay focused on local input handling, integration work, and structured outcome shaping;
- mode semantics should remain a runtime responsibility even when an operation offers local summary text, diagnostics, or supplementary raw detail.

## Probe readiness

A probe is ready when:

- it answers one clear domain question;
- its output fields are minimal but sufficient for downstream use;
- its output fields are domain-natural rather than artificially standardized;
- it does not encode runtime mode semantics such as `check`, `plan`, `explain`, or `next`;
- it does not primarily own shared family prerequisite failures that belong to executable bootstrap;
- its remaining failure modes are narrow, local, and honest;
- its result is understandable from structured outcome fields without relying on raw transport output as the primary contract;
- it is reusable both directly and as a building block for derived probes or workflow-level composition.

Useful review questions:

- what single question does this probe answer;
- which output fields are actually needed by consumers;
- does each field carry distinct machine-relevant meaning;
- are any shared prerequisite failures still incorrectly owned by the probe;
- is any workflow or policy logic leaking into the probe;
- can the result be explained without scraping stdout or stderr;
- would this probe still look clean if reused by another probe or by guard evaluation.

## Bootstrap

A connector may have shared bootstrap or shared context for the whole family.

Shared bootstrap is a distinct layer from operation-to-operation dependency and from workflow-level policy composition.

Bootstrap owns family-wide prerequisites and capability checks that would otherwise make every operation's local failure surface broader and noisier than its narrow semantic job.

Examples:
- `gh` checks binary availability, auth, and required scopes at the family level;
- `gh.issue.view` checks its own local contract;
- `shell` defines supported interpreter policy, while `shell.command` executes a concrete command.

## Dependency layers

Connector design should distinguish at least three dependency layers:

- shared family bootstrap and shared context;
- operation-to-operation implementation dependency when one operation is explicitly derived from another;
- workflow-level composition and policy over public operation results.

These layers should not be collapsed into one another.

Implications:
- shared prerequisites should prefer bootstrap or shared family context rather than being modeled only as ordinary public probes;
- operation-to-operation dependencies are allowed when they stay explicit, local, and reduce semantic duplication;
- workflow-level policy should still compose public operation results rather than being hidden inside implementation dependency graphs;
- canonical fact probes remain preferred over an explosion of narrow policy-shaped derived probes.

## Publicness

`connectors/` is a public and stable layer.

Implications:
- connector and operation names matter;
- family-level semantics matter;
- the meaning of a same-named operation must not change silently.

## Runtime vs connector-library boundary

Connectors should be treated as a built-in public integration library rather than as private runtime internals.
They do not conceptually live inside the runtime core.

Implications:
- runtime owns orchestration, resolution, mode behavior, and explanation flow;
- connector families own integration semantics for their public namespaces;
- runtime consumes connector contracts and results, but should not silently redefine the meaning of connector operations;
- runtime should derive `check`, `plan`, `explain`, and `next` behavior from structured operation contracts and results rather than delegating those mode semantics into connector implementation code;
- runtime should preserve the distinction between family bootstrap state, operation-local outcomes, and workflow-level policy composition when building explanations and plans;
- runtime-facing wiring should flow through an explicit connector-provider surface rather than a hardcoded package location;
- application composition may choose to install the standard built-in connector provider or omit it;
- package placement should preserve this conceptual boundary even when Python packaging or repository layout introduces adapters.

## Connector package structure

The preferred connector package structure is organized first by family, then by operation kind, then by operation file.

Canonical shape:

- `connectors/<family>/bootstrap.py` for family-level bootstrap and shared prerequisites;
- `connectors/<family>/probes/<operation>.py` for one public probe per file;
- `connectors/<family>/actions/<operation>.py` for one public action per file.

Helper files such as `__init__.py` are expected when needed.

Manual central registries that duplicate the package structure should be avoided.

If a public operation exists as a file in the family package tree, that file should be the primary source of truth for its contract and implementation rather than requiring a second hand-maintained registry entry elsewhere.

Family-local autodiscovery or equivalent family-local assembly should be preferred so that each connector family assembles its public probe and action surface from its own package tree.

Operation modules should expose a uniform publication hook so family-local assembly can discover the published operation definition explicitly rather than inferring it from unrelated globals.

## Fixed v0 connector domains

- `git.*`
- `gh.*`
- `shell.*`

## Canonical git probe surface direction

The preferred long-term `git` probe surface is a compact set of repo facts rather than many policy-encoded predicates.

The main target probes are:

- `git.repo`
- `git.branch`
- `git.branches`
- `git.worktree`
- `git.worktrees`
- `git.stash`
- `git.state`
- `git.ref(ref=...)`
- `git.upstream`
- `git.range(base=..., head=...)`

Specialized policy-shaped names such as `git.branch_not_main` are not part of the desired steady-state public surface and should not be added as canonical git probes.

## Possible future connector namespaces

- `run.*`
- `ansible.*`
- `fs.*`
- `obsidian.*`

## Local extension namespaces

- `local.*`
- `project.*`
