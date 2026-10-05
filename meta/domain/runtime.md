# Runtime domain

## Baseline modes

Baseline modes are distinct runtime questions, not necessarily wholly separate evaluation pipelines.
They may share observations, diagnostics, and blocked-state facts, but they differ in primary intent.

Detailed `check` rules live in `meta/model/runtime/check-semantics.md`.
The shared internal analysis-tree model lives in `meta/model/runtime/analysis-tree.md`.

### `review`

Answers whether the authored workflow is structurally strong and explicit enough for humans and agents.

It may report authoring findings such as missing validation, delegated applicability, or weak preflight-support evidence, while staying non-effectful.

It should also distinguish optional-routing step conditions from late admission gates and may recommend `gate` when a long `if` is actually expressing readiness for a mutating step.

For input-related findings, `review` should distinguish between inputs that drive control/effect semantics, trusted profile-provided consumed context, profile-carried ambient surplus, and declared-but-unused inputs rather than treating every declared input as equal validation debt.

Profile-provided consumed context is still meaningful workflow input, but it is not automatically user-driven validation debt.
When a workflow consumes a value such as `repository` from the selected profile as trusted execution context, `review` should not require the workflow to re-validate that context in early guards unless the value also acts as an explicit control-bearing choice.

Its primary value is authoring-quality review rather than executability truth.

`ordo-playbook review` without a workflow name is a playbook-wide static pass. It reports findings grouped by declared workflow from authored playbook and workflow files only. It does not activate a workflow, choose caller inputs, read state, or run probes; contextual checks remain exclusive to `ordo-playbook review <workflow>`.

Its aggregate result labels findings as `blocking` or `advisory`. Missing input descriptions and missing non-user input sources or caller slots are blocking because dependent instruction generation cannot rely on an incomplete input contract. Style and structural recommendations remain advisory; the result separately counts pipe-style recommendations so they are prominent without blocking. The aggregate command exits nonzero for blocking findings or unavailable workflows; this classification and exit behavior do not change `review <workflow>`.

Statically knowable expression mistakes should ideally surface here or in adjacent validation surfaces before `execute` is needed.
For example, a builtin `format` expression whose placeholder count cannot match its argument count is an authoring-time problem, not merely a runtime surprise.

### `check`

Answers whether execution may proceed safely.

It evaluates guard blocks and static prerequisites.
It must not execute effectful business steps.

Its primary value is a safe preflight verdict:
- whether execution is allowed or blocked;
- which guards or prerequisites failed;
- which immediate blockers must be resolved first.

For reachable gated steps, that verdict may also include whether the step can run, cannot run, or cannot yet be established honestly from available read-only knowledge.

That verdict must remain honest about coverage and incompleteness as defined in `meta/model/runtime/check-semantics.md`.

### `plan`

Answers what execution shape is expected.

It builds an explainable plan that shows:
- what will be checked block by block;
- which step blocks are expected to become executable;
- which steps are expected in each step block;
- where execution is blocked.

For gated steps, `plan` should preserve that read-only observations happen before admission is evaluated and that the protected step executes only if the gate passes.

Its primary value is execution preview, not merely blocked-versus-allowed status.

### `execute`

Executes the workflow.

Connector-declared operation kind remains semantically relevant in step context.
A step that references a probe operation is still a read-only probe step and must be dispatched through probe-capable execution semantics rather than through action-only fallback behavior.
Correct probe-step dispatch must not depend on whether execution-tree output is present.

### `explain`

Answers why the runtime reached its current decision.

It returns an explanation of the current runtime decision state, not only of completed execution:
- why execution is blocked or allowed;
- why a guard block failed;
- why a particular guard, step block, or step is relevant to the current outcome;
- why a step was skipped by `if` versus blocked by `gate`;
- which playbook-run profile is active;
- whether that profile came from explicit caller choice or playbook defaults;
- which overrides are active;
- which next action a human or agent can take when that can be inferred safely.

`explain` is a reasoning surface, not merely a verbose restatement of `check` or `plan`.

### `next`

Answers what workflow is the best next safe move in the current playbook context.

Its baseline no-argument meaning is intentionally broad:
- which workflow is runnable now;
- which workflow is the strongest near-ready candidate when nothing is runnable now;
- which missing input or blocker most directly prevents better candidates from becoming runnable;
- why the suggested workflow ranked above nearby alternatives.

`next` is therefore a continuation and recommendation surface, not merely a request to compute the next internal step of one already-selected workflow.

For v1 without explicit predecessor or recovery declarations, runtime should derive `next` from the same shared analysis evidence used by `check` and `explain`, applied across visible playbook workflows.

Its primary value is agent-safe continuation after uncertainty, blockage, or failure rather than effectful execution.

## Why this matters

For agent-authored workflows, `execute` alone is not enough.

The runtime needs modes that:
- reduce risk;
- improve reviewability;
- provide machine-readable reasoning;
- support both coarse-grained and specific questions from humans and agents.

## Runtime ownership of mode semantics

The runtime owns `review`, `check`, `plan`, `execute`, `explain`, and future next-safe-action semantics.
Connector operations should not each reimplement those modes locally.

Runtime may derive these modes from a shared internal decision model.
The modes are distinct query intents over runtime decision state, not necessarily fully separate computation paths.

Instead, runtime should derive higher-level execution meaning from structured operation contracts and structured operation outcomes.

Implications:
- connector operations may provide local observations, effect summaries, diagnostics, and supplementary raw detail;
- runtime combines those local results with workflow block structure, guard evaluation, profiles, and policy to determine authoring findings, blocked state, plan shape, explanation, and next safe action;
- richer runtime modes should come from stronger structured operation surfaces rather than from pushing orchestration logic down into connector implementations.

## Shared analysis-tree boundary

Runtime should prefer one shared context-aware analysis tree rather than separate ad hoc pipelines for `review` and `check`.

That shared tree may preserve partial knowledge under missing inputs, safe read-only observations, structural halt boundaries, and advisory recommendation coverage.

`review` and `check` are sibling projections over that tree:
- `review` reads it for authoring-quality findings;
- `check` reads it for allowed/blocked/unknown runtime truth.

`plan`, `explain`, and `next` should later reuse retained evidence from the same tree rather than reconstructing it from weaker mode summaries.

## Connector dependency direction

The runtime core should be agnostic to the physical location of built-in connectors.

It should depend on:
- connector registry data for resolution;
- probe and action execution capabilities provided through explicit wiring.

It should not depend on a hardcoded connector package path as part of its core semantics.

The runtime is not the semantic owner of built-in connector families.
Built-in connectors should be treated as a public library layer that runtime resolves and executes,
not as private helper code whose public meaning may drift with runtime refactors.

## Composition layer

A composition layer such as CLI bootstrap, application bootstrap, or tests may choose which connector provider to install or pass explicitly.

This layer may:
- use the standard built-in connector provider;
- combine the built-in provider with local or project-specific connectors;
- run with no built-in connector provider at all.

## Activation context boundary

Profiles may carry broader ambient context than any single workflow consumes.

Activation should therefore distinguish between:
- workflow-relevant inputs that the workflow declares or actually consumes;
- surplus profile-carried context that remains available to the run environment but is not part of the workflow's effective input contract.

Profile-supplied surplus context is not, by itself, an activation error.
Workflows should not need to declare unused profile values merely to tolerate reusable profiles with wider context surfaces.
Because such surplus is expected rather than actionable, default `review` and `check` outputs should not promote ordinary profile surplus to user-facing diagnostics.
Surplus-context evidence may remain available internally or in future verbose/debug/explain-oriented surfaces.

This boundary does not erase explicit caller intent.
User-supplied unknown activation inputs remain distinct from profile surplus and should stay diagnosable as explicit caller mistakes or mismatches.
