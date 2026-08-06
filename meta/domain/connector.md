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

Connector operations are also the semantic home for non-trivial transformation and integration logic.
Workflow files may orchestrate them, but should not absorb that algorithmic work into authored workflow structure.

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

An action contract may also expose advisory metadata that helps runtime reason about preflight support quality, for example observation invalidation scopes and recommended preflight-observation templates.

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

## Action readiness

An action is ready when:

- it performs one clear effectful operation within a narrow semantic scope;
- it is an executable leaf operation rather than an abstract namespace or action group;
- its inputs reflect the natural semantic structure of the domain target rather than an artificial scalar-versus-batch normalization;
- its success outputs describe durable effects or effect-relevant observations rather than only a bare success flag;
- it exposes at least one documented action-specific output field on success;
- it does not encode runtime mode semantics such as `check`, `plan`, `explain`, or `next`;
- it validates only facts required for the action to be executable and to remain the action it claims to be;
- it does not hard-code workflow etiquette, safety preferences, or local policy as intrinsic action preconditions;
- distinctions that change the action's result class, failure semantics, or mental model are modeled as separate actions rather than as incidental parameters;
- incidental operational variation that does not change action identity is carried in inputs rather than expanded into many near-duplicate action names;
- its effect boundary is clear enough that a reader can tell what completion of the action actually means;
- if partial effect or partial success is possible, the contract represents that possibility honestly rather than pretending the action is all-or-nothing;
- the meaning of a repeated call is semantically clear, including whether it is idempotent, duplicate, conflicting, additive, or a no-op;
- its resulting post-state is observable through documented outputs, probes, or both;
- when the action creates, selects, moves, or updates an addressable result, that result is returned in a documented addressable form;
- if the action is a true batch operation, its atomic-versus-partial semantics are part of the contract rather than left implicit;
- its remaining failure modes are narrow, local, and honest;
- its documented `failure_modes` describe expected contract-level non-success rather than exceptional runtime breakdown;
- its result is understandable from structured outcome fields without relying on raw transport output as the primary contract;
- it would still make sense if invoked from a different workflow with different surrounding policy.
- if it declares recommended preflight observations, those recommendations remain advisory explainability support rather than hidden executability rules.

Useful review questions:

- what single effect does this action produce;
- is this operation a concrete executable leaf, or only a category that should remain non-executable;
- do the inputs reflect the natural target shape of the domain, or are they forcing an artificial scalar-versus-batch model;
- which output fields are actually needed by consumers to understand what changed;
- is there at least one documented success output field whose meaning is specific to this action rather than generic outcome scaffolding;
- which checks are truly required for executability or action identity, and which are only policy or etiquette;
- does any named variant here actually change result class, failure semantics, or mental model enough to deserve a separate action;
- does any existing action name differ only by incidental parameterization that should instead live in inputs;
- is any apparent batch shape really one aggregated domain target, or is it a set of independent repeated actions;
- where exactly is the action's effect boundary, and what does completion mean;
- can the action produce partial effect or partial success, and if so is that represented honestly in the contract;
- what does a repeated identical call mean here: idempotent retry, duplicate effect, conflict, or no-op;
- is the resulting post-state observable through documented outputs, probes, or both;
- if the action yields an addressable result, is that result returned explicitly enough for downstream use;
- if this is a true batch action, are atomic-versus-partial semantics explicit;
- do the documented `failure_modes` describe expected action-level refusal or non-success, rather than interruption, crash, timeout, or other runtime-level breakdown;
- is any workflow or approval logic leaking into the action;
- can the result be explained without scraping stdout or stderr;
- would this action still look clean if another workflow reused it under a different safety policy.
- if this action advertises recommended preflight observations, do they help `check`, `plan`, and `explain` without assuming one specific workflow-local value source.

## Action input norms

- Action inputs should reflect the natural semantic structure of the target domain rather than an artificially imposed scalar-versus-batch split.
- An action may take no inputs when its target and scope are fully determined by current context.
- When an action operates on one aggregated domain target, it may naturally affect many underlying objects without becoming a batch action.
- A batch action is not merely an action that touches many objects; it is one call that is semantically equivalent to a set of independent repeated actions over multiple targets.
- If multiplicity is an internal property of one domain target, it should remain part of the ordinary action contract rather than being forced into a separate batch surface purely because many objects are involved.
- Inputs should distinguish, when applicable:
  - `target` — what the action is directed at;
  - `payload` — what is created, transmitted, or changed;
  - `constraints` — restrictions that limit the allowed result class;
  - `justification` — explanation or grounds, when the action itself genuinely requires them.
- Free text should be preferred only when the payload structure is inherently unstable or would not produce a useful stable contract shape.
- If an action's inputs grow without clear role separation, this is a signal to review whether the action is too broad or is hiding a small workflow.
- Input differences that only change call data should remain inputs.
- Input differences that change result class, failure semantics, or mental model should lead to separate action leaves rather than one overloaded action surface.

## Contract failure versus exceptional runtime error

- An operation's documented `failure_modes` should describe expected contract-level non-success within the semantic world of that operation.
- Exceptional runtime breakdown must remain distinct from documented contract failure modes.
- Examples of exceptional runtime breakdown include interruption, timeout, transport corruption, uncaught implementation fault, and other failures that do not honestly belong to the operation's narrow domain semantics.
- Connectors should not encode catastrophic or runtime-level breakdown as if it were merely another ordinary business-style action refusal.
- Runtime should preserve the distinction between an operation that failed within contract and an operation whose execution broke down exceptionally.

## Bootstrap

A connector may have shared bootstrap or shared context for the whole family.

Shared bootstrap is a distinct layer from operation-to-operation dependency and from workflow-level policy composition.

Bootstrap owns family-wide prerequisites and capability checks that would otherwise make every operation's local failure surface broader and noisier than its narrow semantic job.

Examples:
- `gh` checks binary availability, auth, and required scopes at the family level;
- `gh.issue.view` checks its own local contract;
- `shell` defines supported interpreter policy, while `shell.command` executes a concrete command.

## Ambient connector execution context

A connector may also depend on ambient execution context that answers questions such as:

- where this connector operates by default;
- which project, directory, file set, account, host, database, or similar attachment point it should use when the operation does not spell that context out again.

This context is not the same thing as connector semantics.
It must not silently redefine the public meaning of connector operations.

Examples:

- `git` may use repository or worktree location context;
- `compose` may use project directory, compose files, or project-name context;
- `mysql` may use host, port, database, or account context.

Such context should be supplied through explicit runtime-owned launch surfaces such as playbook or profile material rather than through hidden process-global assumptions.

The raw family entry from that launch material should be interpreted only by the connector family's bootstrap.
Bootstrap may validate, normalize, reject, or refine that raw input into connector-local shared context for later operations.
Later operation execution should stay inside that connector-local boundary rather than reading raw playbook- or profile-owned connector context directly.

That ambient connector context should not become an ordinary workflow-readable value namespace by default.
Workflow policy should depend on public operation results and other reviewable workflow inputs rather than branching on hidden connector attachment details.

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
- `fs.*`

## Canonical git probe surface direction

The preferred long-term `git` probe surface is a compact set of repo facts rather than many policy-encoded predicates.

The main target probes are:

- `git.repo`
- `git.branch`
- `git.branches`
- `git.tag`
- `git.tags`
- `git.worktree`
- `git.worktrees`
- `git.stash`
- `git.state`
- `git.ref(ref=...)`
- `git.upstream`
- `git.range(base=..., head=...)`

Specialized policy-shaped names such as `git.branch_not_main` are not part of the desired steady-state public surface and should not be added as canonical git probes.

## Possible future connector namespaces

- `compose.*`
- `run.*`
- `ansible.*`
- `obsidian.*`

## Local extension namespaces

- `local.*`
- `project.*`
