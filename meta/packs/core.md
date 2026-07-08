# Ordo core contract

> Generated from meta source docs. Do not edit by hand.

<!-- source: requirements/authoring/core.md -->

# Authoring requirements

## Product quality

- Agent-authorable workflow and profile composition is a core product quality, not a secondary convenience.
- The system must allow a sufficiently capable agent to learn how to compose workflows and profiles from the documented contract surface.
- Authoring support must focus first on workflows, profiles, and related declarative configuration built from existing public operations.
- Fast authoring of new connector families or operations is not a required early-stage customization path.

## Discoverability

- An author must be able to discover which public operations exist and what contracts they expose.
- An author must be able to infer the stable shape of workflows and profiles from schema, examples, and contract documentation.
- The system should prefer composition over invention: composing existing operations and profiles is the default extension path.

## Checkability

- An authored workflow or profile must be machine-checkable before execution.
- The system must help an agent distinguish at least validity, resolution, likely executability, and authoring-quality concerns.
- Validation and explanation surfaces must be structured enough for an agent to iteratively repair an authored workflow without guessing from logs.

<!-- source: requirements/authoring/guard-expressions.md -->

# Authoring requirements for guard expressions

## Compactness

- Guard authoring must support compact declaration of execution conditions.
- Routine policy should usually be readable in a short guard list without requiring a screen of repetitive structural boilerplate.
- A compact guard surface is a core product quality because Ordo exists in part to replace difficult-to-review shell guard logic.

## Discoverability

- An author must be able to tell which parts of a guard expression are public probe invocations and which parts are comparisons over probe results.
- A plain string item in `guards` should be the preferred compact authoring form for expression guards.
- The object form with `uses` should remain available where an explicit operation call is clearer or needed for compatibility.
- Zero-argument probe references should not require empty call syntax when no arguments are being passed.
- Parameterized probe references should remain visually distinct enough that an author can tell inputs are being supplied.
- Workflow input references should be readable as `inputs.name` rather than requiring a template interpolation surface.
- Named arguments should be the preferred authoring form for parameterized probe calls.
- Boolean-valued probe fields should be usable directly as conditions without requiring redundant `== true` boilerplate.

## Preferred authoring surface

- A zero-argument boolean probe fact should read like a compact fact, for example `git.worktree.clean`.
- A zero-argument non-boolean probe value should remain readable through explicit documented field access, for example `git.branch.value`.
- A parameterized probe reference should prefer a compact meta-style call surface, for example `gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).state`.
- The authoring surface should prefer a minimal and orthogonal public probe vocabulary over many specialized policy-encoded probe names.

## Checkability

- Guard expressions must remain machine-checkable and agent-checkable before execution.
- Validation and diagnostics should point to the failing expression segment rather than only reporting a generic guard failure.
- Expression syntax should remain small enough that an agent can learn it from contract docs and examples without treating the workflow format as a hidden programming language.

<!-- source: requirements/connector/core.md -->

# Connector requirements

## Public connector contract

- A workflow must reference stable public connector operations.
- The initial fixed connector domains are `git`, `gh`, and `shell`.
- Connector resolution must preserve stable public semantics independent of local implementation details.
- Project-local profiles and overrides must not silently change the public meaning of a referenced global connector operation.
- Connector operation kinds fixed so far are `probe` and `action`, and they exist only inside connector families.

## Connector result discipline

- Every connector operation must return a structured result on both success and failure paths.
- Every connector operation must preserve that structured result contract even when internal exceptions occur.
- Every connector operation must support narrow local explainability of its own outcome.
- A successful `probe` result must contain meaningful observations or diagnostics, not only a bare success flag.
- A successful `action` result must contain a meaningful effect summary or diagnostics, not only a bare success flag.
- A successful `action` result must expose at least one documented action-specific output field.
- Documented operation `failure_modes` must describe expected contract-level non-success rather than exceptional runtime breakdown.
- Raw stdout/stderr, when produced by an implementation, must be treated as optional detail fields rather than the primary contract surface.

## Extension boundary

- The system must allow project-local extension without forking the global contract.
- Project-specific policy must compose over stable connector operations instead of mutating their meaning.

## Probe addition policy

- Public probes should default to exposing stable observable facts rather than workflow-specific policy verdicts.
- Workflow policy should prefer composition in guard expressions over growth of specialized probe names.
- A new public probe should be added only when at least one of the following is true:
  - it exposes a stable fact that is not otherwise available through existing probe outputs;
  - repeated workflow composition would otherwise require awkward normalization in many places;
  - the needed condition would otherwise force guard-expression language growth beyond compact reviewable policy;
  - the needed condition would otherwise expose unstable operational detail that should remain inside the connector contract.
- A proposed public probe should be rejected when its primary value is merely to avoid a simple comparison or boolean composition in workflow guards.
- Public probe names should avoid encoding local policy, approval decisions, or workflow intent when those can be expressed as guard composition over existing probe results.

## Canonical git probe set

- The canonical `git` probe set should remain small and orthogonal.
- The current target set for broad repo-state coverage is:
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
- This set should be preferred over adding many narrower git probes for local rituals.
- Older specialized policy-shaped probes should not be used as the preferred long-term public surface when the same intent can be expressed through canonical git facts and guard composition.

<!-- source: requirements/playbook/core.md -->

# Playbook requirements

## Discovery and launch surface

- A project-local playbook must be discoverable through a deterministic default location.
- The default discovery rule must be simple enough for both humans and agents to predict without trial-and-error.
- Playbook discovery failure must produce a structured and reviewable error rather than an implicit fallback to unrelated files.
- An explicit playbook path must override default discovery when the caller provides one.

## Catalog and composition

- A playbook must support named workflow entries as the primary launch surface.
- A playbook may support named profile entries for launch-time selection and defaults.
- A playbook launch surface may support explicit launch-time input overrides for one run.
- A playbook workflow entry may declare an explicit execution working directory for that run.
- A playbook workflow entry working directory may use the existing `${...}` value-expression syntax when the expression stays within an activation-time-safe subset.
- A playbook must support named runtime state declarations for project-local reuse.
- A playbook must support binding workflow logical state roles to named project state declarations.
- Every workflow logical state need must have an explicit playbook binding for the active workflow entry.
- Every playbook state binding must target an existing named playbook state declaration.
- Playbook must fail validation when a workflow entry contains a state binding for an undeclared workflow logical state need.
- Playbook-owned names must be unique within their own catalogs.
- Playbook composition must remain explicit rather than relying on silent shadowing or broad filename guessing.

## Resolution discipline

- Relative workflow and profile references must resolve deterministically from playbook-owned context.
- An execution working directory must not change playbook discovery or reference resolution rules.
- A working-directory expression must be fully resolvable before the first guard or step executes.
- Named references must either resolve to one declared target or fail clearly.
- Missing catalog targets must fail validation before effectful execution starts.
- Unknown stable fields in the playbook contract should fail validation.

## Product boundary

- A playbook must remain a project-level launch surface rather than becoming a second workflow language.
- Workflow business logic should stay in workflow files rather than being duplicated into playbook entry definitions.
- Playbook ergonomics should reduce the need for handwritten bootstrap commands without hiding runtime semantics.
- A playbook execution working directory should be explicit runtime context rather than hidden shell-first behavior.
- A playbook working-directory expression must reuse the documented value-expression syntax rather than introducing a second expression language.
- A playbook working-directory expression must not read runtime state, registered step results, or any runtime-derived value that is unavailable at launch time.

<!-- source: requirements/workflow/core.md -->

# Workflow requirements

## Authoring and shape

- A workflow file must be writable by both humans and agents.
- Workflow authoring from existing public operations is a primary product path rather than a niche expert path.
- Validation must fail on unknown fields in stable workflow schema.
- A human reviewer must be able to locate policy and guardrails in the declaration itself rather than reconstructing them from implementation code alone.
- An agent author must be able to predict whether a workflow is valid, resolvable, and likely executable from schema, examples, and connector contracts.
- The contract must minimize hidden shell semantics that change workflow meaning without explicit declaration.
- The default authoring path should favor composition of existing operations and profiles over creation of new connector semantics.
- Explicit workflow-owned data flow between prior and later steps should be representable without inventing connector-local storage hacks.
- Reusable workflow fragments should support explicit local argument contracts.
- Explicit fragment argument contracts must not by themselves force static composition and runtime-scoped invocation to collapse into one reuse primitive when their semantics diverge materially.
- If the product later introduces both `include` and `run`, the distinction must remain brief enough for humans and agents to predict from contract docs and examples.

## Product boundary

- Core semantics must stay small and explainable.
- The format must prefer explicit fields over implicit behavior.
- Drift between docs, schema, examples, and runtime must be detectable.
- Workflow and profile authoring must remain easier and more common than connector authoring in early product stages.

<!-- source: requirements/workflow/value-expressions.md -->

# Workflow requirements for value expressions

## Role

- Workflows may use value expressions for pure local computation of derived values.
- Value expressions exist to keep common normalization and formatting inside workflow authoring without pushing those concerns into connector operations.
- Value expressions are part of workflow authoring surface, not a second orchestration or integration language.

## Allowed capability

- A value expression may read declared workflow inputs.
- A value expression may read declared included-fragment arguments through `args...` when evaluated inside a fragment that declares them.
- A value expression may read runtime state through the documented `state...` read surface.
- A value expression may read prior registered step results through the documented `step...` read surface.
- A value expression may combine multiple local values into one derived value.
- A value expression may apply a closed set of deterministic built-in transforms.
- Inline composition should use the pipe form `|` as the canonical compact authoring surface.
- String formatting may be expressed as a root built-in form.
- A workflow may materialize one derived value through a dedicated pure `value` step form when later steps need to reuse that value through the registered-step read surface.

## Permanent exclusions

- A value expression must never cause side effects.
- A value expression must never call connector operations, whether action or probe.
- A value expression must never read future step results.
- A value expression may evaluate predicates and return boolean values.
- A value expression must never embed control-flow constructs such as conditional branch selection, looping, or step selection.
- A value expression must never choose between alternative values or subexpressions based on a runtime condition, whether through ternary syntax, `if(...)`, `select(...)`, `case(...)`, or equivalent forms.
- A value expression must never duplicate guard or policy semantics as an open-ended boolean language.
- A value expression must never support user-defined functions, macros, operators, or workflow-defined extension hooks.
- A value expression must never become an open-ended collection programming or query language.
- A value expression must never rely on project-defined syntax whose meaning is not part of the stable product contract.

## Readability and reviewability

- Inline value expressions should stay short enough for quick review inside workflow fields.
- Built-in transforms should be understandable left-to-right without reconstructing hidden evaluation rules.
- Validation and diagnostics should identify the failing segment of a value expression rather than only reporting a generic value-resolution failure.

## YAML alternative policy

- Some root built-in value forms may also provide a structured YAML equivalent when inline syntax becomes hard to read.
- YAML equivalence is selective rather than universal.
- Not every inline value expression needs or should have a YAML equivalent.
- A YAML equivalent, when present, should represent the same semantic operation as its inline root form rather than introducing a parallel computation model.
- A dedicated `value` step form, when present, should materialize one already-supported value-expression result rather than introducing a second expression language or a variable-programming surface.

## Growth discipline

- Product growth should prefer adding a small number of high-value built-in transforms over widening value expressions into a general programming language.
- New value-expression capability is a poor fit when it would be better modeled as workflow control, guard policy, connector behavior, or runtime-owned state mutation.
- New value-expression capability is also a poor fit when it would require open-ended semantics for iteration, branching, remote access, or user-defined evaluation.

<!-- source: requirements/runtime/core.md -->

# Runtime requirements

## Runtime behavior

- The runtime must support at least `check`, `plan`, `execute`, and `explain`.
- The runtime must return structured results, not only raw stdout/stderr.
- `plan` must describe what would be checked and executed, including known blockers.
- `explain` must return runtime reasoning in a structured form, not merely debug logs or traceback text.
- The runtime must distinguish at least validation failure, resolution failure, guard failure, execution failure, and success.
- Structured results must be usable by both a human reviewer and an automated agent without log scraping.
- Runtime diagnostics should prefer normalized categories and structured fields over ad hoc human prose.
- The model should support fail-safe behavior for local operational rituals where risk reduction matters more than maximum flexibility.
- The runtime must expose a machine-usable decision surface, not only an execution surface.

## Runtime serialization requirements

- Structured runtime results must be losslessly JSON-serializable.
- `check`, `plan`, `execute`, and `explain` outputs must be consumable without log scraping or YAML parsing.
- Diagnostics, plan items, blockers, inferred next actions, and other contract-level runtime surfaces must be encoded as JSON-shaped fields rather than only human prose.
- Human-readable text may supplement runtime results, but it must not be the only carrier of machine-relevant meaning.

## Agent-facing decision support

- The runtime must be able to answer, in machine-readable form:
  - what is known now;
  - whether execution is allowed now;
  - why execution is blocked when blocked;
  - what next safe action is available when it can be inferred safely.
- `check`, `plan`, and `explain` must remain baseline decision-support modes rather than optional UX sugar around `execute`.

## Explainability

- The system must be able to answer "why is this workflow blocked?" without requiring execution of business steps.
- The system must be able to answer "what would happen if this workflow executed now?" in a machine-readable plan/result shape.
- The system must preserve the difference between:
  - blocked before execution;
  - execution intentionally skipped;
  - execution attempted and failed.
- When a step is intentionally skipped because its `if` condition evaluated to `false`, runtime outputs should preserve that reason in machine-usable form.
- When a step `if` condition cannot be evaluated, the runtime must fail execution rather than silently treating the condition as `false`.
- `explain` output should include useful next actions when the runtime can infer them safely.
- The explanation surface must remain stable enough for agent tooling to rely on status codes and categories.

<!-- source: requirements/runtime/introspection.md -->

# Runtime requirements for introspection

## Role

- The runtime must expose a machine-readable introspection surface for tools and agents.
- This surface exists so external consumers can discover supported contracts and capabilities without prose parsing or direct code-reading.

## Source of truth

- Published introspection must come from runtime-owned metadata or canonical contract data.
- Introspection must not be maintained as a separate descriptive mirror of implementation behavior.
- Human-facing prose may explain the surface but must not define it.

## Minimum surface

The runtime must be able to answer, in machine-readable form:

- what discovery entrypoint exists;
- what workflow and playbook contract surfaces are supported;
- what capability states are supported, unsupported, or planned;
- what expression roots, filters, builtins, and allowed surfaces are supported;
- what public operation metadata is available.

## Growth discipline

- New runtime-visible surface should be added through canonical metadata first or in the same change.
- The project should prefer one shared metadata source over separate runtime and help descriptions.
- Introspection should fail closed for covered surfaces rather than silently omitting changed behavior.

<!-- source: requirements/runtime/state.md -->

# Runtime requirements for state

## Role

- The runtime may expose a small built-in persistent state capability for workflow coordination across runs.
- This capability belongs to runtime rather than to the public connector surface.
- The initial purpose is to remember small pieces of workflow-owned state such as task-to-branch linkage.

## MVP scope

- The initial authoring surface should support a playbook-level `states` mapping that names runtime-managed state locations.
- The initial authoring surface should support workflow-level logical state needs that remain separate from concrete project state declarations.
- The initial workflow `state_needs` surface should be marker-only rather than carrying richer per-need configuration fields.
- The initial authoring surface should support explicit effectful mutation through `state_set` and `state_delete` step forms.
- The initial authoring surface should support direct value reads through `state...` references rather than requiring a dedicated `state_get` step.
- The initial state access grammar should use one aligned path surface for reads, `state_set`, and `state_delete`.
- The initial capability should remain intentionally small and should not require a general-purpose memory or fact system.

## Minimal semantics

- A named state entry should identify a runtime-managed persistent location.
- Workflow state reads and writes should resolve through workflow logical state roles that are bound by the playbook to concrete state declarations.
- A workflow that declares a logical state need is not activatable without a corresponding playbook state binding.
- `state_set` should create or replace the addressed value deterministically.
- `state_delete` should remove the addressed value deterministically.
- State reads should resolve to stored values through the same stable state path surface used by authoring.
- Missing state reads should remain structured and predictable rather than falling back to hidden defaults.
- The initial stable state path should require a logical role, one `inputs...` key reference, and optional dotted field traversal.

## Boundary discipline

- Runtime state should not be modeled as a connector family.
- Runtime state should not be described as a broad fact or knowledge system at this stage.
- Runtime state should not introduce a broad query language, lock model, reconciliation model, or multi-scope memory model in the MVP.
- The MVP should prefer a narrow explicit surface over premature generalization.

<!-- source: requirements/policy/core.md -->

# Policy requirements

## Guard phase

- Guard evaluation must be a first-class runtime phase and not only an informal step convention.
- `check` must evaluate guards and static preconditions without executing effectful business steps.
- A blocked workflow result must identify the blocking guard or guards in machine-readable form.
- The runtime should be able to report more than the first blocking policy issue when such issues can be determined safely without execution.

## Positioning

- Ordo should remain meaningfully distinct from a generic pipeline/task runner by preserving its analysis-first and explain-first behavior.
- Ordo is not required to mimic existing pipeline tools when that would weaken guards, explainability, or structured results.
- Policy evaluation must remain an explicit runtime concern and must not be recoverable only by reading connector implementation code or shell control flow.

<!-- source: requirements/policy/guard-expressions.md -->

# Policy requirements for guard expressions

## Purpose

- Guard policy should be expressible in workflow declarations without requiring a bespoke named probe for every common predicate.
- Policy must remain visible in the workflow rather than being recoverable only from probe implementation details or probe naming conventions.

## Expression scope

- Guard expressions may evaluate only public `probe` operations.
- Guard expressions may compare probe outputs and combine boolean conditions.
- Guard expressions must not call `action` operations.
- Guard expressions must not require a general-purpose expression language with arbitrary functions or user-defined evaluation semantics.

## List semantics

- Each item in `guards` is a separate boolean guard clause.
- The `guards` list combines with implicit `and` semantics across items.
- `or` semantics should be expressed inside one guard expression rather than by overloading list structure.

## Minimum boolean support

- The policy surface should support at least `and`, `or`, `not`, and parentheses for grouping within a single guard expression.
- The policy surface should support at least `==`, `!=`, `in`, and `not in` comparisons needed for common operational predicates.
- Boolean-valued probe facts may appear directly as conditions without an explicit equality comparison.

## Explainability

- Runtime results for failed guard expressions must identify which subcondition evaluated to false or failed to evaluate.
- When a probe inside a guard expression fails operationally, the runtime must preserve the distinction between "condition evaluated false" and "probe could not be evaluated safely".
- Runtime results should preserve a machine-usable evaluation trace rather than only the final blocked guard identity.

<!-- source: domain/authoring.md -->

# Authoring domain

## Role

Authoring is a first-class product surface.

Ordo is not only meant to execute workflows. It must also be understandable and writable by a sufficiently capable agent working from the documented contract surface.

## Primary extension path

The primary extension path in early Ordo is:

- compose workflows from existing public operations;
- compose profiles from explicit presets and policy choices;
- adapt projects through explicit declarative configuration.

The primary extension path is not:

- rapidly inventing new connector families;
- casually creating new operation semantics during routine workflow authoring.

## Discoverability

An author should be able to discover:

- which operations exist;
- what each operation means;
- what inputs and result shapes are expected;
- which examples and patterns are considered idiomatic.

## Checkability

Authoring must be checkable before execution.

An agent should be able to ask, in structured form:

- is this workflow valid;
- are all references resolvable;
- is execution likely blocked now;
- what should be changed to make the declaration better or safer.

## Quality expectation

Good authoring is more than schema validity.

It should preserve:

- explicit intent;
- visible policy;
- reviewability;
- stable public semantics;
- minimal dependence on hidden shell behavior.

<!-- source: domain/connector.md -->

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

<!-- source: domain/playbook.md -->

# Playbook domain

## Role of the playbook

The playbook answers the question:

> which workflows are available in this project, under which names, with which project-local launch context.

It must not answer the question:

> what business steps a workflow performs internally.

## What a playbook owns

- project-local workflow catalog;
- named profile catalog for playbook-run profile selection;
- named runtime state declarations shared across project workflows;
- bindings from workflow-level logical state roles to concrete project state declarations;
- explicit execution working directory selection for project-local workflow entries;
- activation-time derivation of that execution working directory from launch-known inputs only;
- deterministic discovery of the project orchestration root;
- deterministic resolution of project-local workflow and profile references.

## What a playbook does not own

- connector semantics;
- workflow step semantics;
- runtime mode semantics such as `check`, `plan`, `execute`, or `explain`;
- hidden shell-first execution logic.

## Relationship to adjacent domains

- A workflow defines guarded operational intent.
- A profile defines reusable parameters and explicit overrides.
- A playbook defines the project-local launch surface that selects one active profile per run and binds names to workflows, profiles, state declarations, logical state-role bindings, and other explicit execution context such as an entry working directory.
- Runtime still owns mode behavior and execution semantics after playbook discovery and resolution complete.

## Quality bar

A good playbook:

- can be discovered predictably by both humans and agents;
- gives stable names to common project operations;
- keeps project-local launch concerns out of generic workflow logic;
- makes workflow, profile, and state resolution explicit enough for review;
- fails early when catalog entries are missing, ambiguous, or structurally invalid.

## Boundary rule

A playbook is not a workflow.

It is a project-level composition and launch document.
It may select, name, and parameterize workflows through explicit catalogs and defaults,
but it must not absorb the inner business-step logic that belongs in workflow files.

<!-- source: domain/workflow.md -->

# Workflow domain

## Role of the workflow

The workflow answers the question:

> what to check, in what order, and which public operations to call.

It must not answer the question:

> how a transformation or integration algorithm is implemented internally.

## What is acceptable in a workflow

- ordered guard and step blocks;
- reusable included workflow fragments;
- future invocation-oriented reusable fragment runs when static composition is insufficient;
- guard lists inside `guards` blocks;
- ordered steps inside `steps` blocks;
- compact references and parameters that remain workflow-semantic;
- logical state needs that express workflow-owned state roles without naming project storage instances;
- compact parameters;
- simple step-level conditional execution when it has clear semantics.
- simple branching when it has clear semantics.

The stable execution shape is an ordered `blocks` list.
Each block declares exactly one of:

- `guards`
- `steps`

Top-level `guards` and `steps` may remain as compatibility-only authoring sugar when they normalize to the same block structure.

Named launch-time profile selection and project-local state declaration belong to playbook context rather than to generic workflow shape.

Included fragment reuse still belongs to the workflow domain when it remains declarative and workflow-semantic.

`include` specifically belongs to the static-composition side of that workflow reuse story.

If reusable fragments later need caller-scoped runtime modifiers or other invocation semantics, that pressure should be handled by a separate invocation surface such as `run` rather than by widening `include` until it stops being static composition.

That future distinction is acceptable inside the workflow domain because it separates two different jobs:

- `include` for static composition;
- `run` for runtime-scoped reusable-fragment invocation.

## Inclusion boundaries

Included fragments may declare local argument contracts.

Within an assembled workflow:

- `inputs...` remains global workflow input surface;
- `state...` remains global workflow state surface;
- `args...` is local to the included fragment instance that declared it;
- `step...` remains execution-local and must not cross included-fragment boundaries unless a later explicit export model is introduced.

## What is undesirable

- large embedded shell fragments;
- complex text transformations;
- project-specific knowledge baked into a generic workflow;
- hidden side effects.

## Workflow quality

A good workflow:
- can be read quickly from top to bottom;
- can be explained in `plan` and `explain`;
- can be validated before execution;
- can show where one guard barrier ends and the next step sequence begins;
- can be moved across projects while preserving contracts.
- can be authored and iteratively repaired by a sufficiently capable agent using contract docs, examples, and structured diagnostics.

<!-- source: domain/runtime.md -->

# Runtime domain

## Baseline modes

### `check`

Checks guard blocks and static prerequisites.
It must not execute effectful business steps.

### `plan`

Builds an explainable plan:
- what will be checked block by block;
- which steps are expected in each step block;
- where execution is blocked.

### `execute`

Executes the workflow.

### `explain`

Returns an explanation of the runtime decision:
- why a guard block failed;
- why a particular step block or step was chosen;
- which playbook-run profile is active;
- which overrides are active.

## Why this matters

For agent-authored workflows, `execute` alone is not enough.

The runtime needs modes that:
- reduce risk;
- improve reviewability;
- provide machine-readable reasoning.

## Runtime ownership of mode semantics

The runtime owns `check`, `plan`, `execute`, `explain`, and future next-safe-action semantics.
Connector operations should not each reimplement those modes locally.

Instead, runtime should derive higher-level execution meaning from structured operation contracts and structured operation outcomes.

Implications:
- connector operations may provide local observations, effect summaries, diagnostics, and supplementary raw detail;
- runtime combines those local results with workflow block structure, guard evaluation, profiles, and policy to determine blocked state, plan shape, explanation, and next safe action;
- richer runtime modes should come from stronger structured operation surfaces rather than from pushing orchestration logic down into connector implementations.

## Connector dependency direction

The runtime core should be agnostic to the physical location of built-in connectors.

It should depend on:
- connector registry data for resolution;
- probe and action execution capabilities provided through explicit wiring.

It should not depend on a hardcoded connector package path as part of its core semantics.

## Composition layer

A composition layer such as CLI bootstrap, application bootstrap, or tests may choose which connector provider to install or pass explicitly.

This layer may:
- use the standard built-in connector provider;
- combine the built-in provider with local or project-specific connectors;
- run with no built-in connector provider at all.

<!-- source: domain/policy.md -->

# Policy domain

## Guard

A guard is a precondition check evaluated as part of policy before a later effectful step block may run.

A guard is first-class and must not collapse into a hidden step convention.

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

<!-- source: domain/policy-guard-expressions.md -->

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

<!-- source: domain/boundaries.md -->

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

## Boundary rule

Workflow files hold orchestration intent.
Algorithmic transformation lives in connector operation implementation code.

Playbook files hold project-local launch intent and resolution context.
They should not absorb workflow business-step logic.

The runtime is not the semantic owner of built-in connector families.
Built-in connectors should be treated as a public library layer that the runtime resolves and executes, not as private helper code whose public meaning may drift with runtime refactors.
Built-in connectors do not live in the runtime core, even when implementation packaging temporarily places adapter code near runtime-owned modules.
The runtime core should depend on connector-provider wiring abstractions rather than on a specific connector package location.

## Execution rule

Policy evaluation belongs in explicit guards and runtime modes.
Connector code may implement checks, but the workflow/runtime contract must preserve the distinction between:

- blocked before execution;
- planned but not executed;
- executed and failed;
- executed and succeeded.

## Related domain docs

- playbook semantics: `domain/playbook.md`
- connector semantics: `domain/connector.md`
- workflow semantics: `domain/workflow.md`
- runtime semantics: `domain/runtime.md`
- policy semantics: `domain/policy.md`

<!-- source: adr/0004-guard-expressions-prefer-orthogonal-probes.md -->

# ADR 0004: guard expressions prefer orthogonal probes

## Context

Guard expressions exist so workflow policy can remain compact and visible in the declaration.

The current connector surface can drift toward specialized probe names that encode policy directly, for example by exposing many narrow predicates whose only purpose is to avoid writing a simple comparison in the workflow.

That drift weakens one of the main reasons guard expressions exist in the first place.

## Decision

Guard-expression design should prefer a minimal and orthogonal public probe surface.

Policy composition should primarily live in the workflow declaration through guard expressions rather than in a growing catalog of bespoke policy-encoded probe names.

Specialized policy-shaped probes are not the preferred long-term direction and should be avoided in favor of canonical fact probes plus guard composition.

## Consequences

- Public probe contracts should expose stable output fields suitable for documented guard-expression field access.
- New connector work should avoid adding specialized policy probes unless a strong public-contract reason exists.
- Drift between meta examples and connector naming should be resolved by moving toward more orthogonal probe contracts rather than by normalizing policy sprawl into the connector layer.

<!-- source: model/workflow/entities.md -->

# Workflow entities

## Main entities

- `Playbook`
- `Workflow`
- `WorkflowFragment`
- `FragmentArg`
- `FragmentRun` (planned)
- `StateNeed`
- `OperationRef`
- `Guard`
- `Step`
- `Profile`
- `Override`
- `Connector`
- `ConnectorBootstrap`
- `OperationContract`
- `ExecutionPlan`
- `OperationResult`
- `ExecutionResult`
- `Diagnostic`

## Key relations

- A `Playbook` names project-local workflow entries, profile entries, and runtime state declarations.
- A `Workflow` contains ordered `Guard` and `Step` entries.
- A `Workflow` may include reusable `WorkflowFragment` instances through ordered include items inside its block structure.
- A future `Workflow` surface may invoke reusable `WorkflowFragment` instances through ordered `run` step forms inside `steps` blocks.
- A `WorkflowFragment` may declare local `FragmentArg` entries and workflow payload content.
- A planned `FragmentRun` would express runtime-scoped invocation of one reusable `WorkflowFragment` with an explicit caller/callee boundary while still reading like one workflow step.
- A `Workflow` may declare logical `StateNeed` entries that are bound by the active playbook workflow entry.
- A `Guard` references an `OperationRef`.
- A `Step` is either an operation-call step that references an `OperationRef` or a built-in runtime step form.
- A `Step` may declare an `if` condition that controls whether that one declared step executes or is skipped.
- A `Step` may publish an execution-local registered result for later steps through a workflow-local `register` identifier.
- A `Connector` groups operations and can own shared bootstrap/runtime prerequisites.
- A `Profile` supplies reusable parameters or composition defaults.
- An `Override` changes resolution explicitly, never silently.
- An `OperationContract` describes public inputs, outputs, effects, and failure modes.
- An `ExecutionPlan` describes checks, steps, and blockers without requiring effectful execution.
- An `OperationResult` captures structured connector-level outcome details.
- An `ExecutionResult` contains status plus diagnostics and outputs.

## Boundary reminder

- `Playbook` expresses project-local launch intent and resolution context.
- `Workflow`, `Guard`, and `Step` express orchestration intent.
- `StateNeed` expresses workflow-level need for persistent state without naming concrete project storage instances.
- Step conditions express per-step eligibility, not first-class branch topology.
- Built-in runtime step forms may be effectful, such as state mutation, or pure, such as value materialization.
- Registered step results express execution-local data flow, not persistent workflow state.
- Fragment arguments express local reusable-fragment binding, not global workflow input redefinition.
- Included-fragment boundaries keep registered `step...` data local unless a later explicit export surface is introduced.
- A future fragment-run boundary should keep caller-local `step...` data explicit at the call site rather than treating it as implicit fragment-body scope.
- They do not own connector implementation algorithms.
- `Profile` and `Override` express composition and explicit local adaptation.
- `Diagnostic` and execution/result entities carry machine-usable analysis and runtime surfaces.

<!-- source: model/playbook/shape.md -->

# Playbook model shape

## Position

The playbook is the project-local orchestration root.

Canonical path in the initial model:

```text
.ordo/playbook.yml
```

## Minimal shape

```yaml
version: 1

states:
  repo_task_state:
    path: .ordo/state/task-state.json

defaults:
  profile: backend-default

workflows:
  inspect-issue:
    file: inspect-issue.yml

  close-task:
    file: close-task.yml
    working_directory: ${inputs.repo_root}
    state_bindings:
      task_memory: repo_task_state

profiles:
  backend-default:
    file: backend-default.yml
```

## Stable top-level concepts

- `version` — playbook contract version;
- `states` — named project-local runtime state declarations;
- `workflows` — named launchable workflow entries;
- `profiles` — named launchable profile entries;
- `defaults` — optional playbook-run defaults such as the active profile.

## Workflow entry role

A workflow entry gives a stable project-local name to a workflow file.

It may additionally declare:

- state bindings from workflow logical roles to concrete playbook state entries;
- an explicit execution `working_directory` for runs of that workflow entry, expressed either as a literal path string or as an activation-time-safe `${...}` value expression;
- future launch metadata that remains project-local rather than workflow-semantic.

## Defaults role

Playbook defaults apply to one playbook run.

The initial important default is:

- `defaults.profile` — the default active profile for the run when the caller does not select one explicitly.

## Profile entry role

A profile entry gives a stable project-local name to a profile file.

The profile file contributes runtime activation context for one playbook run.

That context may include:

- input bindings;
- approved overrides;
- future runtime-facing execution selectors that remain declarative and reviewable.

Profiles do not create a second orchestration language.
They make project-local launch context explicit and reviewable.

## State entry role

A state entry gives a stable project-local name to a runtime-managed state location.

The initial standard field is:

- `path` — storage path or location identifier.

Future state metadata such as format, initialization policy, or backend kind may extend the state entry shape when runtime semantics standardize them.

## State binding role

A workflow entry may bind workflow logical state roles to concrete playbook state entries.

This keeps workflow authoring focused on logical state usage such as `task_memory`,
while the playbook owns the concrete project binding such as `repo_task_state`.

## Activation rule

The initial playbook model assumes one workflow per run.
The run selects one active profile, applies that profile, and then activates one named workflow entry.

<!-- source: model/playbook/discovery.md -->

# Playbook discovery model

## Default discovery rule

When the caller does not provide an explicit playbook path, CLI should look for:

```text
.ordo/playbook.yml
```

relative to the current working directory.

## Explicit playbook path

When the caller provides an explicit playbook path, that path becomes the discovery result and default discovery is skipped.

## Initial simplicity rule

The initial model should prefer a small and predictable discovery rule over aggressive filesystem search.

Implications:

- no silent fallback from `playbook.yml` to unrelated filenames;
- no broad directory crawling as a hidden convenience mechanism;
- no dependence on shell aliases or external wrappers for the canonical discovery rule.

## Failure rule

If default discovery does not find `.ordo/playbook.yml`, runtime should return a structured missing-playbook outcome rather than guessing a workflow file.

## Future extensions

Possible future behaviors such as parent-directory search or alternate filenames should remain explicit additions to the model rather than being assumed by convention.

<!-- source: model/playbook/resolution.md -->

# Playbook resolution model

## Resolution base

Resolution starts from the directory that contains the discovered playbook file.

For the canonical default path:

```text
<project>/.ordo/playbook.yml
```

the resolution base is:

```text
<project>/.ordo/
```

## Named workflow resolution

When CLI is asked to run a named workflow entry such as `close-task`, it resolves that name through `workflows.<name>` in the playbook.

The entry must resolve to exactly one workflow file.

## Workflow file resolution

- A bare workflow filename such as `close-task.yml` resolves under `<playbook-dir>/workflows/`.
- A relative workflow path containing directory segments resolves relative to `<playbook-dir>/`.
- An absolute workflow path remains absolute.

## Profile reference resolution

- A bare named profile reference such as `backend-default` resolves through `profiles.<name>` in the playbook.
- A bare profile filename such as `backend-default.yml` resolves under `<playbook-dir>/profiles/`.
- A relative profile path containing directory segments resolves relative to `<playbook-dir>/`.
- An absolute profile path remains absolute.

## Active profile resolution

- Each playbook run selects at most one active profile.
- If the caller specifies a profile explicitly, that selection wins.
- Otherwise `defaults.profile` becomes the active profile when present.
- If no explicit profile and no default profile are present, the run proceeds without a profile.
- Active profile resolution happens before workflow activation and step execution.

## Execution working directory

- A workflow entry may declare `working_directory` as explicit runtime context for runs of that entry.
- `working_directory` may be either a literal path string or a `${...}` value expression that resolves to a path string.
- A `working_directory` expression reuses the existing value-expression syntax but with a narrower activation-time surface.
- The activation-time surface may read only launch-known input values.
- The activation-time surface must not read `state...`, `step...`, or any other runtime-derived value.
- The activation-time surface must resolve fully before the first guard or step executes.
- After expression evaluation, a relative `working_directory` path resolves relative to `<playbook-dir>/`.
- After expression evaluation, an absolute `working_directory` path remains absolute.
- When present, runtime executes the workflow with that resolved working directory as the execution working directory.
- Runtime may restore its prior process working directory after the run completes, but that restoration behavior must not be part of workflow semantics.
- `working_directory` changes execution context only; it must not change playbook discovery, workflow/profile reference resolution, or state-path resolution.

## Launch-time input overrides

- A playbook run may accept explicit launch-time input overrides from the caller.
- Launch-time input overrides apply to the selected workflow run only.
- Launch-time input overrides take precedence over workflow-declared input defaults.
- Launch-time input overrides also take precedence over profile-provided missing-input defaults.
- A launch-time input override may be provided either inline or from a file-backed raw string value.
- Launch-time input overrides do not mutate the playbook, workflow source file, or profile source file.

## State resolution

- Playbook state names resolve through `states.<name>`.
- A relative state `path` resolves relative to `<playbook-dir>/`.
- An absolute state `path` remains absolute.

## Workflow state binding resolution

- Workflow state reads and writes address logical roles through `state.<role>...`.
- The active workflow entry resolves those logical roles through `state_bindings.<role>`.
- Each bound value must resolve to one declared playbook state entry.
- Every workflow-declared logical state role must resolve through `state_bindings.<role>`.
- Missing state bindings fail before effectful workflow execution begins.
- Extra state bindings that do not correspond to declared workflow logical state roles fail validation.

## Resolution discipline

- Resolution must be deterministic.
- Ambiguous implicit matches are not allowed.
- Playbook resolution must complete before effectful workflow execution begins.

<!-- source: model/workflow/value-expressions.md -->

# Workflow value expressions

## Position

Value expressions provide a compact workflow-owned surface for deriving values from local runtime-visible inputs and prior registered step results.

They sit between two existing surfaces:

- plain scalar values with no runtime evaluation;
- connector operations and built-in runtime step forms that carry effects.

They are intended for local shaping of values, whether inline inside workflow fields or materialized through a dedicated pure value step, not for orchestration, policy, or integration logic.

Step conditions may also reuse the `${...}` envelope for local boolean evaluation over the same workflow-visible roots.

## Core expression forms

The initial model supports three author-facing forms inside `${...}`:

- direct references such as `inputs.name`;
- direct references to included-fragment arguments such as `args.repository`;
- direct references to prior registered step results such as `step.issue.outputs.id`;
- left-to-right filter pipelines using `|`;
- root built-in calls such as `format(...)`.

Illustrative examples:

```yaml
${inputs.repository}
${args.repository}
${state.task_state[inputs.task_key].branch}
${step.issue.outputs.id}
${inputs.title | slug}
${inputs.title | trim | slug | truncate(60)}
${format("{}/{}-{}", inputs.type | lower, inputs.issue_number, inputs.title | slug)}
```

## Expression roots

The workflow-facing value-expression roots are:

- `inputs...` for declared workflow inputs;
- `args...` for declared included-fragment arguments local to the current fragment instance;
- `state...` for persistent runtime state reads;
- `step...` for prior registered step results.

The `step...` root is execution-local and order-sensitive.

It must not cross included-fragment boundaries in the MVP.

It is not a persistent storage surface.

## Filter pipeline

The pipe form `|` is the canonical compact composition surface.

It should be read left to right:

1. resolve the value on the left;
2. apply each built-in transform in order;
3. produce one final derived value.

The pipeline model is intentionally narrow:

- each stage is pure and deterministic;
- each stage consumes the previous stage output;
- the pipeline does not imply connector execution, control flow, or collection programming.

## Root built-ins

Some value operations are better expressed as a dedicated root built-in form than as an ordinary pipeline stage.

The first supported root built-in is `format(...)`.

Illustrative inline form:

```yaml
${format("{}/{}#{}", inputs.owner, inputs.repo, inputs.number)}
```

`format(...)` exists because workflows often need to compose multiple local values into one string while preserving a compact, reviewable surface.

## Boolean use in step conditions

When a value expression appears in a workflow step condition, it may participate in limited boolean composition through `and`, `or`, `not`, and parentheses.

This boolean layer exists for local workflow-owned condition evaluation over `inputs...`, `args...`, `state...`, and prior `step...` results.

It may combine direct boolean references and boolean-producing predicate expressions, including existing pipeline forms that end in a boolean result.

This does not permit connector or probe calls and does not turn value expressions into the public guard-expression surface.

## YAML equivalent forms

Some root built-ins may also define a structured YAML equivalent.

The structured equivalent is determined by the root expression form, not by arbitrary subexpressions inside the inline syntax.

The first dual-form built-in is `format`.

Illustrative YAML form:

```yaml
branch:
  format: "{}/{}-{}"
  args:
    - ${inputs.type | lower}
    - ${inputs.issue_number}
    - ${inputs.title | slug}
```

This YAML form exists for readability when the equivalent inline `format(...)` call becomes too dense.

Simple filter pipelines such as `${inputs.title | slug}` do not require a YAML equivalent.

## Initial built-in set

The initial built-in set should stay intentionally small.

Illustrative MVP set:

- `lower`
- `trim`
- `slug`
- `truncate(n)`
- `replace(from, to)`
- `format(...)`

This set is closed product surface, not workflow-defined or project-defined syntax.

## Examples

Branch name assembly:

```yaml
${format("{}/{}-{}", inputs.type | lower, inputs.issue_number, inputs.title | slug | truncate(60))}
```

Safe file name assembly:

```yaml
${format("{}_{}-{}-issue{}.md", inputs.ts, inputs.owner, inputs.repo, inputs.issue_number)}
```

Structured alternative for a longer formatted value:

```yaml
branch:
  format: "{}/{}-{}"
  args:
    - ${inputs.type | lower}
    - ${inputs.issue_number}
    - ${inputs.title | trim | slug | truncate(60)}
```

## Non-goals

Value expressions are not meant to become:

- a connector invocation surface;
- a second guard-expression language;
- an embedded conditional value-selection language;
- a general-purpose programming language;
- a workflow-defined macro system;
- an open-ended query or collection-transformation language.

They may evaluate predicates and participate in limited boolean composition for step-condition semantics, but they must not choose between alternative values or subexpressions based on a runtime condition.

Illustrative forbidden forms include ternary syntax and helpers such as `if(...)`, `select(...)`, or `case(...)`.

They also must not read future step results or smuggle step-result access into guard evaluation.

## Value-step relation

A workflow may also materialize one derived value through a dedicated built-in `value` step form when later steps should reuse that derived result through the normal `step.<register>...` surface.

Illustrative form:

```yaml
steps:
  - name: compute-branch-name
    value:
      format: "{}/{}-{}"
      args:
        - ${step.project.outputs.type | lower}
        - ${step.issue.outputs.number}
        - ${step.issue.outputs.title | slug}
    register: branch
```

This does not introduce a second computation model.

The `value` step merely materializes one already-supported workflow value into a registered step result so later steps may read it without recomputing the same expression.

<!-- source: model/workflow/guard-expressions.md -->

# Guard expression model

## Concept

A guard expression is a boolean predicate evaluated when its containing guard block runs.

It is modeled as policy over public probe results rather than as a general embedded program.

## Allowed semantic elements

- boolean literals and other JSON-shaped literals suitable for comparison;
- references to workflow inputs such as `inputs.issue`;
- zero-argument public probe references;
- parameterized public probe references;
- documented field access over probe outputs;
- boolean composition;
- comparison operators.

## Probe reference semantics

- A plain string item in `guards` denotes a compact guard expression.
- A zero-argument probe reference may appear without empty call syntax.
- A parameterized probe reference carries explicit named arguments in the preferred authoring form.
- Within one guard expression, repeated identical probe references should be evaluated once and reused.
- A probe reference inside an expression must resolve against the same public probe contract surface used by explicit operation-form guards.
- A public probe surface used by expressions should remain as orthogonal as practical rather than encoding many bespoke policy predicates in probe names.
- A new probe should not be introduced merely to avoid a short comparison, boolean composition, or small membership check over existing probe outputs.

## Output access semantics

- Field access after a probe reference means reading documented structured output from that probe result.
- Field access is not a general object method system.
- Public contract documentation must define which output fields are stable enough to reference from guard expressions.
- A boolean-valued field may be used directly as a condition.
- Non-boolean probe outputs should be compared through explicit documented field access such as `git.branch.value`.

## Guard list semantics

- A workflow may contain multiple guard items inside one `guards` block.
- Each guard item yields a boolean pass/fail outcome or an evaluation failure.
- Multiple guard items combine as an ordered conjunction over the guard list.

## Failure semantics

- A false comparison result means the guard blocks execution.
- A probe evaluation failure inside an expression is not the same thing as a false comparison result.
- Guard explanation should preserve both the boolean structure and the probe-level outcome details.
- Guard evaluation must remain side-effect free.
- A statically invalid field path should fail before runtime guard evaluation begins.

<!-- source: model/runtime/lifecycle.md -->

# Workflow lifecycle

## Minimal lifecycle

1. Parse
2. Validate
3. Resolve connector operations
4. Evaluate guards
5. Build plan / explain
6. Execute steps
7. Emit structured result

## Blocking states

- validation failed
- resolution failed
- guard failed
- execution failed

<!-- source: model/runtime/state.md -->

# Runtime state model

## Position

Runtime state is a built-in runtime capability for small persistent workflow-owned values.

Its declaration point belongs to playbook-level project orchestration context rather than to individual workflow files.

It is not:

- a connector family;
- a replacement for external source-of-truth systems;
- a general-purpose memory subsystem in the initial model.

## Top-level declaration

Playbooks may declare named runtime state locations through a top-level `states` mapping.

Minimal shape:

```yaml
states:
  repo_task_state:
    path: .ordo/state/task-state.json
```

The initial model treats the declared value as a runtime-managed location identifier. The first backend may be file-backed.

Workflow files consume logical state roles through `state.<role>...` references and state mutation step forms.
The playbook binds those logical roles to declared project state entries.
If a workflow declares a logical state role, activation requires a corresponding playbook binding.

The initial `state_needs` contract is marker-only.
It declares that a workflow needs a named logical role such as `task_memory`,
but it does not yet add per-need schema, purpose, kind, or capability subfields.

Illustrative binding shape:

```yaml
workflows:
  close-task:
    file: close-task.yml
    state_bindings:
      task_memory: repo_task_state
```

## Mutation step forms

State mutation uses dedicated built-in step forms rather than connector `uses` references.

Set example:

```yaml
state_needs:
  task_memory: {}

steps:
  - name: remember-branch
    state_set:
      state.task_memory[inputs.task_key].branch: ${inputs.branch}
```

Delete example:

```yaml
steps:
  - name: forget-branch
    state_delete: state.task_memory[inputs.task_key].branch
```

These forms are effectful runtime operations even though they do not go through the public connector registry.

## Read surface

State reads use direct references instead of a dedicated retrieval step.

Illustrative form:

```yaml
${state.task_memory[inputs.task_key].branch}
```

The read surface should stay aligned with the mutation target surface so that authors do not learn two unrelated addressing models.

## Stable path grammar

The initial stable state path grammar is:

```text
state.<role>[inputs.<key-reference>][.<field>...]
```

Examples:

- `state.task_memory[inputs.task_key]`
- `state.task_memory[inputs.task_key].branch`
- `state.task_memory[inputs.task_key].metadata.owner`

Read usage wraps the same path inside a value expression:

```yaml
${state.task_memory[inputs.task_key].branch}
```

Mutation targets use the same path text directly:

```yaml
state_set:
  state.task_memory[inputs.task_key].branch: ${inputs.branch}

state_delete: state.task_memory[inputs.task_key].branch
```

## Initial grammar restrictions

- the path must start with `state.`;
- `<role>` is an identifier-like logical state role name;
- the bracketed key reference must use dotted `inputs...` form;
- at least one segment must follow `inputs` inside the key reference;
- field traversal after the key is optional and uses dotted identifiers only;
- the initial grammar does not support literal keys, quoted keys, multiple bracket segments, arbitrary nested expressions, or mixed index syntaxes.

## MVP constraints

- The initial model should remain centered on named state locations and addressed values.
- State declaration ownership should remain at playbook level so workflows do not duplicate project-local storage setup.
- Workflow authoring should use logical state roles rather than concrete project state instance names.
- A declared workflow logical state role is a required composition dependency rather than an optional hint.
- The initial state-need contract should stay marker-only until runtime owns a clear reason for richer per-need fields.
- The initial model should not assume multiple state scopes beyond explicitly declared named entries.
- The initial model should not require bulk update semantics, query semantics, or concurrency semantics.
- The initial model should not rename this capability into a larger semantic system before the runtime actually owns those broader concerns.

<!-- source: model/runtime/guard-evaluation.md -->

# Guard evaluation runtime model

## Role

Guard evaluation is part of the runtime decision surface, not only a hidden implementation detail.

## Minimum runtime structure

- A failed guard result must identify the blocking guard item.
- A failed guard result must identify the failing subcondition when available.
- Runtime outputs should preserve observed values when they materially explain the outcome.
- Runtime outputs should preserve a machine-usable evaluation trace rather than collapsing everything into a single boolean.

## Outcome distinctions

Runtime guard evaluation must preserve the distinction between:

- validation failure before guard evaluation;
- resolution failure before guard evaluation;
- boolean guard failure where evaluation completed and the condition was false;
- probe evaluation failure where the condition could not be safely evaluated.

## Trace expectations

- The trace should preserve boolean structure closely enough for explanation.
- Probe-level observations should remain attributable to the probe reference that produced them.
- A repeated identical probe reference within one expression should be reusable without requiring duplicate probe execution.

<!-- source: model/runtime/package-layout.md -->

# Package layout

## v0 Python package shape

The minimal v0 package layout is:

- `ordo.model` — public domain models for workflow, profile, connector, diagnostic, and runtime result.
- `ordo.runtime` — runtime orchestration entry points and mode-specific logic.
- `connectors` — built-in public connector library packages, organized by family.
- `ordo.connectors` — runtime-facing adapter and registry surface over the built-in connector library.
- `ordo.types` — shared JSON-shaped value aliases used by public model surfaces.

## Model split inside `ordo.model`

- `workflow` owns `Workflow`, `OperationRef`, `Guard`, and `Step`.
- `profile` owns `Profile` and explicit `Override` data.
- `connector` owns `Connector`, family bootstrap data, and `OperationContract`.
- `diagnostic` owns normalized machine-usable diagnostics.
- `runtime` owns runtime mode, plan, operation result, and result envelope data.

## Boundary rule

Package layout must preserve the contract boundary:

- workflow models hold orchestration intent;
- connector models hold public operation contracts;
- runtime models hold decision and result surfaces;
- helper modules must not smuggle hidden runtime semantics into the model layer.

## v0 discipline

- The layout must stay small enough to explain directly from the public contract.
- It must support YAML authoring and JSON-shaped runtime surfaces.
- It must support `check`, `plan`, `execute`, and `explain` without treating connector authoring as the routine customization path.

## Connector library shape

The built-in connector library should live under the repository-level `connectors/` tree.

`ordo.connectors` may provide adapter and registry entry points for the runtime, but it should not become the primary home of family implementations.
The runtime core should reach built-in connectors through provider-style wiring, not through a hardcoded assumption about where family code lives.

A separate composition layer should decide whether the standard built-in connector provider is installed by default for a particular application surface.

Even when connector code is imported through `ordo.connectors`, the conceptual boundary remains:

- `ordo.runtime` is the engine and orchestration layer;
- `connectors` is the built-in public connector library consumed by the runtime;
- `ordo.connectors` is the runtime-facing adapter surface over that library.

The import path may be package-local for implementation convenience, but that should not blur ownership of connector semantics.
Built-in connectors should not be modeled as part of the runtime core merely because they are shipped with the same distribution.

Connector packages should follow the family-first layout:

- `connectors/<family>/bootstrap.py` for family-level bootstrap;
- `connectors/<family>/probes/<operation>.py` for a single public probe module;
- `connectors/<family>/actions/<operation>.py` for a single public action module.

This layout should be preferred over monolithic cross-family modules and over hand-maintained central registries that duplicate operation declarations outside the family package tree.

Assembly should prefer family-local autodiscovery or an equivalent family-local mechanism rather than a cross-family hand-edited registry list.

<!-- source: model/connector/contract.md -->

# Connector and operation contract

## Connector

Connector is a public family-level contract.

Connector owns:
- namespace
- shared bootstrap
- family-level prerequisites
- shared runtime context
- operation registry

## Operation

Operation is a public callable unit inside a connector.

Current operation kinds:
- `probe`
- `action`

Operation contract must define:
- inputs
- prerequisites
- effects
- outputs
- failure modes

Here, `prerequisites` means operation-local prerequisites that are part of the public contract of that specific operation.
Shared family prerequisites belong to connector bootstrap rather than to every operation contract entry.

Operation contract may also expose lifecycle metadata when needed, for example whether an operation is deprecated and which canonical operations should replace it.

## Explainability and failure normalization

Every operation must:
- return a structured result on both success and failure paths
- support narrow local explanation of its own outcome
- normalize internal exceptions into a structured failure result rather than escaping as the only observable surface

When an implementation produces raw stdout/stderr, those streams are secondary details inside the result contract, not the primary contract itself.

## Minimal structured operation outcome surface

To stay small and mode-agnostic while still supporting runtime `check`, `plan`, `explain`, and future next-safe-action behavior, an operation outcome should expose at least:

- `status` — the operation-local normalized outcome
- `summary` — a short human-readable local explanation
- `outputs` — the structured observations or effect summary that carry the operation's machine-relevant meaning
- `diagnostics` — structured local problems, warnings, or refusal detail when needed
- `raw` — optional supplementary transport or implementation detail such as stdout, stderr, return code, or response fragments

Implications:
- probes should place their durable observed facts in `outputs` rather than in summary text alone
- actions should place their durable effect summary in `outputs` rather than in summary text alone
- `raw` is supplementary detail and must not be the only place where contract-relevant meaning exists
- runtime mode semantics should be derived from this structured local surface rather than pushed down into operation-specific mode logic

## Contract split

### Family-level

Connector-level bootstrap may check and prepare shared prerequisites.

Examples:
- binary exists
- auth is available
- shared scopes or session context

### Operation-level

Operation checks only its own local contract.

Examples:
- input shape
- required target object
- operation-specific flags
- operation-local prerequisites not already guaranteed by connector bootstrap

## Rule

Shared prerequisites should not be duplicated in every operation contract if they are already owned by connector bootstrap.

<!-- source: model/connector/authoring-surface.md -->

# Connector operation authoring surface

## Purpose

Connector operation authoring should stay small, local, and mode-agnostic while still exposing enough structure for runtime `check`, `plan`, `explain`, and future next-safe-action behavior.

This authoring surface exists to keep connector code readable without pushing runtime orchestration semantics down into each probe or action.

## Operation module responsibilities

An operation module should be responsible for:

- declaring its local operation contract;
- exposing a uniform publication hook for that operation module;
- accepting local inputs through a narrow authoring context;
- performing local integration work;
- returning a structured local outcome.

An operation module may also depend on other operations when that dependency is explicit, local, and part of the narrow integration semantics of the derived operation.

An operation module should not be responsible for:

- reimplementing runtime modes;
- knowing workflow-level orchestration policy;
- constructing the public runtime result envelope directly;
- embedding `check`, `plan`, `explain`, or `next` semantics in handler-local control flow.

## Uniform publication hook

Each operation module should expose a uniform publication hook such as `info()`.

That hook should publish the operation as a whole rather than leaving metadata and execution behavior as unrelated module globals.

Implications:

- the publication hook is distinct from the execution handler;
- the execution handler remains the operation's execution point rather than the module's publication point;
- runtime or connector-family discovery should read the operation module through this uniform publication hook;
- simple operation modules should not rely on ad hoc naming magic to bind contract metadata to execution behavior.

## Minimal authoring context

The authoring context should stay narrow.

At minimum it should support:

- access to operation-local inputs;
- reusable helpers for local integration work such as command execution;
- inline failure mapping for repetitive transport-level failures;
- narrow local context needed for diagnostics or execution environment details.

It should not require connector handlers to receive broad runtime-shaped objects such as full workflow state or resolution internals when the operation does not need them for its local job.

## Minimal structured outcome surface

At minimum an authored operation outcome should expose:

- `status` — normalized local outcome;
- `summary` — short local human-readable explanation;
- `outputs` — structured observations or structured effect summary;
- `diagnostics` — structured local problem detail when needed;
- `raw` — optional supplementary transport or implementation detail.

Implications:

- probes should place durable observed facts in `outputs`;
- actions should place durable effect facts in `outputs`;
- summary text helps reviewability but must not be the only contract-relevant meaning;
- raw detail is supplementary and must not be required to recover the main outcome semantics.

## Failure mapping expectations

Repeated transport-level failure handling should be supported by reusable authoring helpers rather than copied `if` ladders in every operation.

Typical examples include:

- command spawn failures;
- non-zero command exit handling;
- transport response normalization.

Domain-specific negative outcomes should still remain visible in operation-local Python logic when they are part of the operation's narrow semantic job.

## Dependency expectations

The authoring surface should distinguish between:

- shared bootstrap or family capability state;
- explicit operation-to-operation dependency;
- workflow-level composition over public results.

Implications:

- a small operation should not be forced to rediscover every shared family prerequisite by itself;
- derived operations may reuse other operations explicitly when that keeps semantics clearer and avoids duplication;
- operation-to-operation reuse should not become hidden runtime magic;
- workflow and policy composition should remain visibly distinct from operation implementation dependency.

## Runtime-owned semantics

Runtime should derive higher-level mode behavior from operation contracts and structured outcomes.

The authored operation outcome is a local authoring-facing outcome surface, not the full public runtime result envelope.

Runtime owns:

- blocked-versus-runnable interpretation in workflow context;
- plan assembly;
- workflow-level explanation;
- next-safe-action reasoning;
- mapping local operation outcomes into the public runtime result envelope.

## Migration direction

Current connector implementations may still be authored against runtime-shaped models during migration.

The target direction is a dedicated connector authoring surface or plugin SDK that preserves:

- simple local operation code;
- stable structured outcomes;
- runtime ownership of orchestration semantics.

<!-- source: model/connector/bootstrap-api.md -->

# Concrete executable bootstrap API proposal

## Role

This document defines the first concrete executable bootstrap API proposal for connector families.

Its purpose is to turn family bootstrap from metadata-only declaration into a real executable capability-check layer while keeping the pattern close to the existing publication-hook direction for operations.

## Bootstrap module shape

Each connector family bootstrap module should expose exactly two primary surfaces:

- `info()` — the uniform publication hook for the family bootstrap definition;
- `run(ctx)` — the bootstrap execution hook.

The publication hook is the family bootstrap publication point.
The execution hook is the family bootstrap execution point.

## Publication hook

The uniform publication hook should be:

```python
def info() -> PublishedBootstrap
```

`info()` should return the published bootstrap definition for the family.

The first executable bootstrap step should not require additional family-bootstrap globals beyond this publication hook.

## Published bootstrap definition

The minimal published bootstrap definition should expose at least:

- `prerequisites`
- `context_fields`
- `handler`

Implications:

- `prerequisites` describe shared family prerequisites rather than operation-local prerequisites;
- `context_fields` describe the family-level capability or context facts that bootstrap may provide on success;
- the published definition does not need operation-style `inputs`, `outputs`, `effects`, or `failure_modes` fields unless later code proves they are necessary.

## Execution hook

The bootstrap execution hook should be:

```python
def run(ctx: BootstrapContext) -> BootstrapOutcome
```

The hook should remain family-capability-oriented rather than operation-oriented.
It should not know which specific probe or action will later consume the bootstrap state.

## Bootstrap context

The minimal bootstrap context should expose at least:

- `command(argv, *, failures=...)` for command-backed capability checks;
- narrow environment access needed to discover shared family context;
- a way to report or accumulate shared capability facts when bootstrap succeeds.

The first executable bootstrap step should not require workflow-level policy state or operation-local inputs.

## Bootstrap outcome

The minimal bootstrap outcome should expose at least:

- `status`
- `summary`
- `diagnostics`
- `raw`
- `context`

Where:

- `status` reports bootstrap success or bootstrap failure at the family layer;
- `summary` gives a short human-readable family-level result;
- `diagnostics` carries structured bootstrap problems or warnings;
- `raw` carries supplementary command or transport detail when helpful;
- `context` carries shared family capability facts made available to later operation execution.

The bootstrap outcome is a connector-family capability result, not an operation result and not the full public runtime envelope.

## Command helper expectations

Bootstrap should be able to use the same low-level command helper pattern as operations where appropriate.

The minimum normalized failure keys for the first executable bootstrap step should be:

- `os_error`
- `nonzero`

Additional keys may be added later if executable bootstrap checks prove they are needed.

## Runtime expectations

Runtime should evaluate executable family bootstrap before operation-local logic when a family requires shared prerequisites.

Runtime should then:

- preserve bootstrap success or failure as its own layer;
- carry bootstrap `context` into later operation execution;
- keep bootstrap failures distinct from operation-local failures and workflow-policy outcomes.

## Git first-step expectations

For the Git family, the first executable bootstrap step should be able to detect at least:

- missing `git` binary;
- non-repository context.

On success, it may provide shared facts such as:

- repository root;
- repository availability confirmation.

Additional facts such as current branch should be included only if keeping them at bootstrap level remains semantically clean.

## Low-ceremony requirement

Bootstrap authoring should stay small and direct.

The first executable Git bootstrap should not require substantially more ceremony than a small probe module, except for the extra family-level context field in its outcome.

If executable bootstrap grows into a second large authoring framework, the boundary should be reconsidered before wider rollout.

## Open questions intentionally left to code work

The first bootstrap implementation step should answer these by code rather than by abstract generalization:

- whether bootstrap should share the exact command helper implementation with operation context or only the same pattern;
- whether bootstrap diagnostics need anything beyond the current local diagnostic shape;
- whether bootstrap `context` should remain an unstructured mapping at first or immediately grow a richer view type;
- whether runtime should cache bootstrap state per family per run or simply reevaluate it at the first straightforward integration point.

<!-- source: model/connector/plugin-sdk.md -->

# Connector plugin SDK sketch

## Role

The connector plugin SDK is the concrete authoring-facing surface that should realize the connector authoring boundary.

It exists to let operation files stay small, local, and readable without importing core runtime models directly.

## Design goal

For a simple operation such as `git.branch`, the SDK should allow a single-file implementation that:

- declares its operation contract locally;
- executes narrow local integration work;
- returns a structured local outcome;
- avoids unnecessary incidental technical ceremony.

Simple operation files should not need avoidable scaffolding such as broad runtime-shaped arguments or unnecessary `from __future__ import annotations` imports.

## Minimal SDK entities

The SDK should expose only a small set of authoring-facing entities.

At minimum:

- operation metadata type for probes;
- operation metadata type for actions;
- uniform publication-hook return type for operation modules;
- narrow operation context type;
- structured operation outcome type;
- structured local diagnostic type;
- reusable local integration helper result types where needed.

The SDK should prefer one small coherent surface over many narrowly sliced helper types.

## Metadata expectations

Operation metadata should let an authored module declare at least:

- operation name;
- operation kind;
- inputs when applicable;
- outputs;
- failure modes;
- effects when applicable.

Metadata should remain local to the operation module rather than requiring a second hand-maintained registry declaration elsewhere.

The SDK should support a uniform publication hook such as `info()` that returns the published operation definition for the module.

That published definition should bind operation metadata and execution handler explicitly.

## Context expectations

The operation context should stay narrow and authoring-oriented.

At minimum it should support:

- operation-local input access;
- reusable command execution for command-backed operations;
- inline failure mapping for repetitive transport-level failures;
- narrow execution-environment access when needed for local behavior or diagnostics;
- explicit access to shared family bootstrap state or shared capability context when the operation depends on it.

The context should not require small operations to know workflow internals, guard-expression internals, or runtime mode state.

When operation-to-operation reuse is allowed, the SDK should prefer an explicit local dependency surface over hidden runtime magic.

## Command helper expectations

Command-backed operations are expected to be common.

The SDK should therefore provide a command helper that:

- executes a command locally;
- normalizes repetitive transport-level failure categories;
- supports inline failure mapping close to the call site;
- returns a structured helper result suitable for local domain-specific checks after the command succeeds technically.

This helper exists to avoid repeated low-level `if` ladders for command spawn failure, non-zero exit handling, and similar transport concerns.

## Outcome expectations

The SDK outcome type should preserve the minimal structured operation outcome surface already defined elsewhere in meta:

- `status`;
- `summary`;
- `outputs`;
- `diagnostics`;
- `raw`.

The SDK may provide convenience constructors or helpers for common success and failure cases, but those helpers must not hide the structured outcome model itself.

For example, a helper that constructs a single structured diagnostic together with a failure outcome is a good fit for the SDK when it reduces repeated boilerplate across many operations without inventing a second failure abstraction.

## Low-ceremony requirement

The SDK should optimize for low incidental ceremony in small operation files.

Implications:

- simple probes and actions should fit comfortably in one small file;
- import surfaces should stay small;
- common success and failure paths should be concise;
- repeated one-diagnostic failure shaping should not require each operation to rebuild the same local helper function;
- publication should remain explicit without requiring ad hoc module-global binding conventions;
- operation code should remain more prominent than authoring-framework boilerplate.

## Runtime boundary

The SDK is not a second runtime.

It should not re-expose:

- workflow orchestration semantics;
- runtime mode semantics;
- full runtime result-envelope assembly;
- policy evaluation logic.

Those remain runtime responsibilities.

## Dependency-layer boundary

The SDK should help keep three layers distinct:

- family bootstrap and shared capability state;
- explicit operation-to-operation reuse;
- workflow-level policy composition.

It should not encourage simple technical prerequisites to masquerade as arbitrary public probe graphs, and it should not hide derived-operation dependencies behind opaque runtime behavior.

## Expected migration use

The first migration step should be able to prove the SDK shape on one or two very small operations before broader connector migration begins.

If the resulting operation code is not visibly simpler and more local than the current runtime-shaped form, the SDK shape should be reconsidered before wider adoption.

The concrete first-spike API proposal should live in a separate model document so code work can implement the SDK without reconstructing it from principles alone.

Executable family bootstrap should likewise have its own concrete model document so shared prerequisite evaluation can be implemented explicitly rather than inferred from metadata-only bootstrap declarations.

<!-- source: model/connector/plugin-sdk-api.md -->

# Concrete plugin SDK API proposal

## Role

This document turns the bounded plugin-SDK sketch into a concrete minimal authoring API proposal for the first implementation spike.

The goal is not to freeze every future detail.
The goal is to make the first code implementation possible without guesswork.

## Module-level shape

Each operation module should expose exactly two primary surfaces:

- `info()` — the uniform publication hook for the module;
- `run(ctx)` — the execution handler for the published operation.

The publication hook is the module's publication point.
The execution handler is the operation's execution point.

## Publication hook

The uniform publication hook should be:

```python
def info() -> PublishedOperation
```

`info()` should return a published operation definition that binds contract metadata and the execution handler explicitly.

Simple modules should not require any additional publication globals.

The first spike should not require operation-level ordering hints such as per-module `ORDER` values.
Operation publication should remain complete without a separate operation-order side channel.

## Published operation definition

The minimal published operation definition should expose at least:

- `name`
- `kind`
- `handler`
- `inputs`
- `outputs`
- `failure_modes`
- `effects`
- `prerequisites`

Implications:

- probe modules may leave `inputs`, `effects`, or `prerequisites` empty when not needed;
- action modules may leave `effects` empty only when the action has no narrower effect summary to declare;
- `prerequisites` here means operation-local prerequisites, not shared family bootstrap prerequisites.

The first spike may use separate published-definition types for probes and actions if that keeps the API simpler.

## Execution handler

The execution handler should be:

```python
def run(ctx: OperationContext) -> OperationOutcome
```

The first spike may use separate `ProbeContext` and `ActionContext` types only if the difference is concrete and small.
If the difference is weak, one `OperationContext` is preferred.

The handler should stay mode-agnostic.
It should not know whether runtime is currently building `check`, `plan`, `execute`, `explain`, or next-safe-action behavior.

## Operation context

The minimal context should expose at least:

- `input(name)` or equivalent access to operation-local inputs;
- `command(argv, *, failures=...)` for command-backed integration work;
- `bootstrap()` or equivalent access to shared family bootstrap/capability state;
- `call(name, *, inputs=None)` or equivalent explicit operation-to-operation dependency surface;
- narrow environment access when needed for local diagnostics or execution details.

The first spike should prefer plain, explicit names over abstraction-heavy helper layering.

## Command helper

The concrete command helper should support this shape or a shape very close to it:

```python
ctx.command(
    ["git", "branch", "--show-current"],
    failures={
        "os_error": "git_unavailable",
        "nonzero": "probe_failed",
    },
)
```

The minimum normalized failure keys for the first spike should be:

- `os_error`
- `nonzero`

Additional keys such as timeout handling may be added later only if the first migrated operations need them.

## Command result

The command helper result should expose at least:

- `stdout`
- `stderr`
- `returncode`
- `raw`

If additional convenience accessors are introduced, they should remain small and obviously derived from those core fields.

## Operation outcome

The concrete local outcome type should expose exactly the structured surface already defined elsewhere in meta:

- `status`
- `summary`
- `outputs`
- `diagnostics`
- `raw`

The first spike should prefer one shared `OperationOutcome` shape unless probe/action differences require a second type in practice.

## Diagnostic type

The minimal local diagnostic type should expose at least:

- `code`
- `level`
- `message`
- `details`

Path-heavy runtime-specific structure should remain outside the local plugin SDK unless a first migrated operation proves it necessary.

## Convenience helpers

The first spike may provide small convenience helpers such as:

- `ok(...)`
- `fail(...)`
- `fail_with_diagnostic(...)`

Those helpers should only construct `OperationOutcome` values more concisely.
They should not replace or obscure the underlying structured outcome model.

`fail_with_diagnostic(...)` is appropriate when many operations would otherwise repeat the same pattern of:

- `status`
- `summary`
- one structured diagnostic code and message
- optional `details`
- optional `raw`

The helper should stay small and explicit rather than growing hidden policy or operation-kind-specific semantics.

## First-spike example shape

The intended first-spike authoring style is approximately:

```python
def info() -> PublishedOperation:
    return PublishedProbe(
        name="branch",
        outputs={"value": "string"},
        failure_modes=("git_unavailable", "not_repository", "probe_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    command = ctx.command(
        ["git", "branch", "--show-current"],
        failures={
            "os_error": "git_unavailable",
            "nonzero": "probe_failed",
        },
    )

    branch = command.stdout.strip()
    if not branch:
        return fail(
            code="probe_failed",
            summary="Current branch could not be determined",
            raw=command.raw,
        )

    return ok(
        summary="Current branch inspected successfully",
        outputs={"value": branch},
        raw=command.raw,
    )
```

This example is intentionally small.
If the first migrated files need substantially more ceremony than this, the SDK API should be reconsidered before wider rollout.

## Open questions intentionally left to the spike

The first implementation spike should answer these by code rather than by further abstract discussion:

- whether one `OperationContext` is enough or probe/action split pays for itself;
- whether one `PublishedOperation` type is enough or probe/action split pays for itself;
- whether operation-to-operation dependency should use operation names or richer refs locally;
- whether `bootstrap()` should return one shared object or named capability views;
- whether convenience helpers are useful enough to keep after the first migrated operations.

<!-- source: model/connector/resolution-policy.md -->

# Resolution policy

## Baseline

Workflow references are resolved against public connector operations.

## Default policy

- same-name silent shadowing is not default behavior
- base public connector semantics must remain stable
- local adaptation must be explicit

## Allowed local adaptation

- local namespaces such as `local.*` or `project.*`
- explicit override mechanisms, if the runtime exposes them
- profiles as composition/preset layer

## Not allowed by default

- silent replacement of `gh.*`, `git.*`, or `shell.*`
- same-name semantic drift hidden from workflow readers

## Why

Workflow readability and portability depend on visible resolution semantics.

<!-- source: data/workflow/shape.md -->

# Workflow data shape

## Stable top-level fields

- `version`
- `workflow`
- `inputs`
- `state_needs`
- `blocks`

Compatibility-only top-level fields:

- `guards`
- `steps`

The stable execution shape is block-based.
Top-level `guards` and `steps` remain compatibility inputs that normalize to `blocks`.

## Stable block shape

```yaml
blocks:
  - guards:
      - git.worktree.clean
  - steps:
      - name: verify
        uses: shell.run
        with: {}
```

Rules:

- `blocks` is an ordered non-empty list;
- each block item must declare exactly one of `guards`, `steps`, or `include`;
- `guards` block value is a non-empty guard list;
- `steps` block value is a non-empty step list;
- an `include` block item references one included workflow fragment and may optionally bind `with` values for declared fragment `args`;
- block order is semantically meaningful;
- a `guards` block is evaluated before any later `steps` block may run.

Current stable shape note:

- `run` is not part of the current stable block shape.
- A future invocation-oriented step form may add `run` under `steps:` rather than changing the meaning of existing `include` items.

Stable include item form:

```yaml
- include: github/check-issue
  with:
    repository: ${inputs.repository}
    issue_number: ${inputs.issue_number}
```

Include item rules:

- `include` is a non-empty string reference to an included workflow fragment;
- `with` is optional and, when present, is an object;
- `with` keys bind only declared fragment `args` keys;
- include expansion preserves block order in the assembled workflow.

## Planned fragment run step shape

Illustrative future form:

```yaml
- steps:
    - name: comment-and-status
      run: github/comment-and-set-status
      if: ${step.issue.outputs.open}
      with:
        comment: "Issue is open."
        status: "In Progress"
```

Planned run step rules:

- `run` would be a non-empty reusable-fragment reference on one step entry;
- `name` would remain required because the author-facing surface still treats the invocation as one step;
- `with` would remain the explicit fragment-argument binding object;
- `if` would be evaluated in caller scope rather than in fragment-body scope;
- the invoked fragment would execute with its own fragment-local `args...` and `step...` scope.

## Included fragment document shape

Illustrative included fragment file:

```yaml
description: Check one issue and reuse the loaded result
args:
  repository: string
  issue_number:
    type: integer
  project_id:
    type: string
    default: null
  dry_run:
    type: boolean
    default: false

blocks:
  - steps:
      - name: inspect
        uses: gh.issue
        with:
          repository: ${args.repository}
          issue_number: ${args.issue_number}
```

Rules:

- an included fragment may declare `description`;
- an included fragment may declare `args` as a mapping of fragment-local argument names;
- an `args` entry may use a short scalar declaration such as `repository: string` for a required argument;
- an `args` entry may use an object declaration with fields such as `type`, `required`, and `default`;
- `default` may be any JSON-shaped value, including `null`;
- an omitted optional argument and an explicit `null` binding are distinct authoring cases;
- fragment-local argument reads use the `args.<name>` surface;
- included fragment payload content must still normalize to ordinary workflow block semantics after argument binding and expansion.

## Compatibility normalization

Illustrative legacy form:

```yaml
guards:
  - git.worktree.clean

steps:
  - name: verify
    uses: shell.run
    with: {}
```

Normalized form:

```yaml
blocks:
  - guards:
      - git.worktree.clean
  - steps:
      - name: verify
        uses: shell.run
        with: {}
```

Normalization rules:

- if `blocks` is present, top-level `guards` and top-level `steps` must not be present;
- if `blocks` is absent, at least one of top-level `guards` or top-level `steps` must be present;
- top-level `guards` normalizes to one leading `guards` block;
- top-level `steps` normalizes to one trailing `steps` block.

## Stable guard shape

```yaml
- uses: namespace.name
  with: {}
```

## Stable logical state need shape

```yaml
state_needs:
  task_memory: {}
```

The initial stable shape is marker-only.

Implications:

- each logical state role name maps to an empty object;
- additional per-need fields are not part of the initial stable contract;
- unknown nested fields under a logical state need fail validation.

## Stable step shape

```yaml
- name: some-step
  uses: namespace.name
  with: {}
```

Built-in runtime state mutation forms may also appear in `steps`.

Stable state target/read path grammar:

```text
state.<role>[inputs.<key-reference>][.<field>...]
```

Rules:

- reads use this path only inside `${...}`;
- `state_set` keys use this path text directly;
- `state_delete` uses this path text directly;
- the key reference inside `[...]` must use dotted `inputs...` form;
- post-key field traversal uses dotted identifiers only.

Set example:

```yaml
- name: remember-branch
  state_set:
    state.task_memory[inputs.task_key].branch: ${inputs.branch}
```

Delete example:

```yaml
- name: forget-branch
  state_delete: state.task_memory[inputs.task_key].branch
```

Workflow files do not declare runtime state locations themselves.
They declare logical state needs and reference them through the `state.<role>...` read and mutation surface.

Unsupported or ambiguous variants are outside the initial stable contract.

## Current rule

Unknown top-level and nested stable fields fail validation.

## Serialization rule

- Workflow files may be authored in YAML.
- Workflow semantics are defined over the loaded data model, not over YAML-specific syntax.
- Stable workflow data must be representable as a losslessly JSON-serializable structure after loading.
- YAML-specific mechanisms such as anchors, aliases, tags, or merge behavior must not introduce distinct runtime semantics unless explicitly standardized.

<!-- source: data/playbook/shape.md -->

# Playbook data shape

## Stable top-level fields

- `version`
- `states`
- `workflows`
- `profiles`
- `defaults`

## Stable workflow entry shape

```yaml
workflows:
  close-task:
    file: close-task.yml
    state_bindings:
      task_memory: repo_task_state
```

Required field:

- `file`

Optional stable field:

- `state_bindings`

Stable `state_bindings` shape:

```yaml
state_bindings:
  task_memory: repo_task_state
```

## Stable defaults shape

```yaml
defaults:
  profile: backend-default
```

Optional stable field:

- `profile`

## Stable profile entry shape

```yaml
profiles:
  backend-default:
    file: backend-default.yml
```

Required field:

- `file`

## Stable state entry shape

```yaml
states:
  task_state:
    path: .ordo/state/task-state.json
```

Required field:

- `path`

## Serialization rule

- Playbook files may be authored in YAML.
- Playbook semantics are defined over the loaded data model, not over YAML-specific syntax.
- Stable playbook data must be representable as a losslessly JSON-serializable structure after loading.
- YAML-specific mechanisms such as anchors, aliases, tags, or merge behavior must not introduce distinct runtime semantics unless explicitly standardized.

## Current rule

Unknown top-level and nested stable fields fail validation.

<!-- source: data/workflow/guard-expressions.md -->

# Guard expression data shape

## Stable guard forms

Guards may be expressed either as explicit operation calls or as compact expressions.

### Operation-call form

```yaml
- uses: namespace.name
  with: {}
```

### Expression form

```yaml
- git.worktree.clean and git.branch.value != "main"
```

```yaml
- gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).state != "CLOSED"
- gh.project.issue(repository=inputs.repository, issue_number=inputs.issue_number, project_id=inputs.project_id).exists
```

## Expression shape rules

- A string guard item contains a compact boolean policy expression.
- A string guard item is the preferred compact authoring form for expression guards.
- Zero-argument probe references do not require `()`.
- Parameterized probe references use argument syntax only when arguments are present.
- `inputs.name` is the stable input-reference form inside expressions.
- Named arguments are the preferred parameter syntax for probe calls.
- Field access after a probe reference reads probe output fields.
- Boolean-valued probe fields may appear directly as conditions.
- Expression grammar remains intentionally small and dedicated to guard evaluation.

## List semantics

- Multiple string or object guard items may appear in one `guards` list.
- The list structure itself implies conjunction across items.
- Disjunction belongs inside a single expression item rather than in the list structure.

## Coexistence rule

- Both guard forms may coexist during migration if the product needs compatibility between explicit probe calls and compact expression guards.
- The stable contract may allow both object-form guards and string-form guards during migration without requiring a tag field for expression guards.

## Serialization rule

- Guard expression meaning is defined over the loaded workflow model, not over incidental YAML formatting.
- Any parsed guard expression must still map to a losslessly explainable runtime structure.

<!-- source: data/runtime/result-envelope.md -->

# Result envelope

## Minimal envelope

The runtime result must be able to express:

- overall status
- failed guard or failed step
- diagnostics
- outputs
- skipped/executed steps

Connector operation results must also preserve enough structure for the runtime to expose:

- meaningful observations for successful probes
- meaningful effect summaries for successful actions
- structured failure diagnostics even when the underlying implementation raised an exception
- optional raw stdout/stderr detail fields when an implementation produces them

At minimum, a connector operation outcome should preserve:

- operation-local `status`
- short local `summary`
- structured `outputs` carrying observations or effect summary
- structured `diagnostics` when local problem detail matters
- optional supplementary `raw` detail

This operation outcome is the connector-local structured input to runtime adaptation, not the entire public runtime result envelope by itself.

## Serialization constraints

- The public runtime result envelope is JSON-shaped.
- Contract-level result fields must be losslessly JSON-serializable.
- Python-specific, transport-specific, or format-specific value kinds must not be required by the public result contract.
- Human-readable summaries may be included, but machine-relevant meaning must remain available in structured fields.

## Baseline statuses

- `ok`
- `guard_failed`
- `validation_error`
- `resolution_error`
- `execution_error`

<!-- source: scenarios/core.md -->

# Core scenarios

## Scenario 1: guarded repo ritual

Workflow checks local repo state, confirms guardrails, and executes a small sequence of repo actions.

Expected Ordo value:

- guard barriers are visible before the affected steps run;
- runtime can say whether the ritual is blocked before any business action happens;
- result can tell both human and agent what to fix next.

## Scenario 2: GH-backed issue workflow

Workflow reads GitHub issue/project state through stable `gh.*` operations and composes policy at workflow/profile level.

Expected Ordo value:

- workflow policy is expressed in declarations rather than buried in shell branching;
- connector operations keep stable public semantics while project policy stays local;
- `plan` and `explain` can show issue-state blockers separately from git-state blockers.

## Scenario 3: local project override

Project adds local connector operations or profiles without changing baseline global connector semantics.

Expected Ordo value:

- local adaptation stays explicit;
- reviewers can see where a project extends behavior versus where it consumes shared contracts;
- runtime diagnostics can mention active overrides rather than silently changing behavior.

## Scenario 4: plan before execute

Agent or human asks for `plan`/`explain` before performing effectful steps.

Expected Ordo value:

- runtime returns a machine-readable plan;
- blocked steps are distinguishable from merely not-yet-run steps;
- the caller can decide whether to continue to `execute`.

## Scenario 5: non-git effector

Workflow invokes `shell.*` without assuming git-centric design.

Expected Ordo value:

- shell remains an effector, not the dominant semantic layer;
- explainability still works even when shell is involved;
- the workflow contract remains more stable than opaque shell strings alone.

## Scenario 6: multiple blockers before execution

Workflow is blocked by more than one policy issue at once, for example:

- dirty worktree;
- current branch is `main`;
- issue status is not eligible.

Expected Ordo value:

- `check`/`explain` can surface multiple blockers in one result when safe to do so;
- human does not have to fix issues one-by-one through repeated fail-fast loops;
- agent can choose the safest next question or remediation.

## Scenario 7: policy-heavy close-task ritual

Workflow for shipping/closing a task depends on repo kind, verification profile, git safety checks, and issue/project state.

Expected Ordo value:

- repo-specific verification can be selected via profiles without hiding the high-level ritual intent;
- runtime can explain why merge/close is blocked before attempting side effects;
- final result can show which checks passed, which were skipped, and which blocked execution.

## Scenario 8: agent asks what is allowed now

Agent inspects a repo and asks what action is currently safe:

- only check;
- plan available but execute blocked;
- execute allowed.

Expected Ordo value:

- runtime status is explicit enough to drive agent behavior;
- no brittle parsing of shell logs is required;
- decision support is part of the runtime contract, not an afterthought.

## Scenario 9: explainable failure, not just execution failure

User wants to know not only that a workflow failed, but whether it:

- failed validation;
- failed resolution;
- was blocked by guards;
- failed during step execution.

Expected Ordo value:

- these categories remain distinct in the result surface;
- user and agent get a clearer recovery path;
- the project stays different from a generic step runner that mainly exposes logs and exceptions.

<!-- source: scenarios/playbook/core.md -->

# Playbook scenarios

## Scenario 1: project-local workflow catalog

Repo exposes a small named set of common operational workflows through `.ordo/playbook.yml`.

Expected Ordo value:

- humans can discover available operations quickly;
- agents can target named workflows without reconstructing local bootstrap commands;
- project launch ergonomics improve without changing workflow semantics.

## Scenario 2: default profile selection

Playbook run selects a default profile such as `backend-default` before activating one workflow.

Expected Ordo value:

- common project defaults stay reviewable in one place;
- workflow files remain less repo-specific;
- callers may still override profile selection explicitly.

## Scenario 3: shared project state declaration

Multiple workflows use one named runtime state entry such as `task_state` declared in the playbook.

Expected Ordo value:

- state naming stays stable across workflows;
- storage location is managed in project-local orchestration context;
- workflows do not each duplicate the same storage declaration.

## Scenario 3b: launch-time input override

Caller launches a named workflow entry but needs to override one input such as `repository`, `issue_number`, or `enabled` for a single run.

Expected Ordo value:

- the caller can override or add the input without editing the workflow file;
- launch-time values win over workflow defaults and profile-provided defaults;
- the override remains local to that one run.

## Scenario 4: logical workflow state binding

Workflow uses a logical state role such as `task_memory`, while the playbook binds that role to a concrete state entry such as `repo_task_state`.

Expected Ordo value:

- workflow files stay portable across projects with different storage naming;
- playbook owns project-local storage binding rather than workflow files;
- missing bindings fail clearly before effectful execution.

## Scenario 5: missing playbook on default discovery

Caller runs `ordo plan close-task` in a directory without `.ordo/playbook.yml`.

Expected Ordo value:

- failure is immediate and explicit;
- runtime does not guess a workflow file from nearby YAML;
- both human and agent receive a clear next step.

## Scenario 6: unresolved named workflow

Playbook contains a named workflow entry whose target file no longer exists.

Expected Ordo value:

- validation or pre-execution resolution fails before effectful work;
- diagnostics name the missing entry and its target;
- the project can repair the catalog without inspecting runtime internals.

## Scenario 7: missing required state binding

Workflow declares `state_needs.task_memory`, but the active playbook workflow entry does not bind `task_memory`.

Expected Ordo value:

- activation fails before effectful execution;
- diagnostics identify the missing logical state role;
- runtime does not attempt to guess or auto-create a binding.

<!-- source: scenarios/authoring.md -->

# Authoring scenarios

## Human authoring

Human writes or reviews a workflow using readable connector operations, small schema surface, and examples.

Human should be able to answer, by reading the declaration:

- what policy is enforced;
- which guards can block execution;
- which steps are intended after each guard barrier passes;
- whether shell is being used as an escape hatch or as the main hidden mechanism.

## Agent authoring

Agent writes a workflow against schema + examples + connector contracts and can predict validation/runtime behavior.

This is not a marginal scenario. It is one of the main intended ways the product is used.

Agent should be able to predict:

- whether `uses` references are valid and resolvable;
- what `check` and `plan` would return in broad shape;
- what categories of failure are possible;
- which result codes are safe to branch on programmatically.

Agent should also be able to determine that the better next step is to compose an existing workflow/profile from public operations rather than invent a new connector operation.

## Mixed maintenance

Human and agent can evolve the same workflow without hidden local semantic traps.

This implies:

- local overrides stay explicit;
- public operation semantics stay stable;
- workflow meaning does not silently drift into implementation details only a shell expert can reconstruct.

## Review scenario

Reviewer should be able to tell whether a proposed workflow is:

- a clear declaration of policy and intent;
- an opaque shell script disguised as YAML;
- safe for an agent to invoke in `check`/`plan` mode.

## Composition-first scenario

Agent needs a new local ritual.

Preferred path:

- inspect available public operations and examples;
- compose a workflow from existing operations;
- add or adjust a profile when local policy or defaults differ;
- run machine-checkable validation and explanation before any execution.

Discouraged default path:

- invent a new connector family or new public operation semantics just to express routine local variation.

## Explainability scenario

Both human and agent should be able to use runtime explanation without replaying failure manually.

Desired experience:

- reviewer asks "why is this blocked?" and gets a structured answer;
- agent asks "what can I safely do next?" and gets machine-readable status plus next actions;
- explanation quality does not depend on scraping unstructured stderr.

<!-- source: scenarios/workflow/guard-expressions.md -->

# Guard expression scenarios

## Short review scenario

Reviewer opens a workflow and should be able to see, in a small vertical slice:

- which conditions gate execution;
- which conditions are simple facts versus comparisons;
- which actions follow if those conditions pass.

## Shell-replacement scenario

A project has sprawling local shell helpers with many execution preconditions.

Desired migration experience:

- move operational integration details into public probes and actions;
- keep workflow policy compact enough that the preconditions are easier to read than the original shell control flow;
- avoid replacing shell sprawl with a long list of repetitive structured guard blocks.

## Agent authoring scenario

Agent composes a workflow from documented public probes and actions.

Desired experience:

- use compact expressions for ordinary policy;
- avoid inventing a new named probe only to express a simple comparison such as equality, inequality, or membership;
- receive diagnostics that identify the failing subcondition and observed value.

<!-- source: adr/0001-scope.md -->

# ADR 0001: scope

## Decision

Ordo is a local declarative ritual engine, not a general distributed workflow platform.

## Why

This keeps the core small, explainable, and suitable for operational helper workflows.

<!-- source: adr/0002-connectors-are-public.md -->

# ADR 0002: connectors are public

## Decision

`connectors/` is a public contract layer.

## Why

Workflow portability and explainability depend on stable connector and operation semantics.

## Consequence

Silent same-name semantic shadowing must not be the default behavior.

<!-- source: adr/0003-packs-are-derived.md -->

# ADR 0003: packs are derived

## Decision

`meta/packs/**` is generated from source docs under `meta/{requirements,domain,model,data,scenarios,adr,verification}`.

## Why

This keeps source-of-truth documents editable while allowing compact derived packs for agents and later tooling.

<!-- source: verification/core/drift.md -->

# Verification

## Drift checks

At minimum the project must be able to check:

- workflow examples validate against schema;
- generated packs are in sync with source docs;
- public docs do not contradict core contract docs;
- connector contract changes are reflected in examples and schema where relevant.

## Review rule

If schema or runtime semantics change, corresponding `meta/` source docs must change in the same work.

<!-- source: verification/connector/invariants.md -->

# Connector invariants

## Core invariants

- workflows reference only public connector operations
- fixed v0 connector domains are `git`, `gh`, and `shell`
- connector semantics are public and stable
- connector operation kinds fixed so far are `probe` and `action`
- connector operations preserve structured results on success, failure, and exception paths
- `probe` remains semantically read-only and `action` remains the effectful operation kind
- silent same-name shadowing is not default behavior

## Drift rule

If a change breaks any invariant, `meta/` must be updated explicitly in the same work.

<!-- source: verification/playbook/core.md -->

# Playbook verification

## Rule

Playbook must provide a deterministic and reviewable project-local launch surface.

## Checks

- `.ordo/playbook.yml` discovery behavior is documented and testable.
- Missing playbook, missing workflow entry, and missing profile entry fail with distinct structured outcomes.
- Workflow names are unique within the playbook workflow catalog.
- Profile names are unique within the playbook profile catalog.
- State names are unique within the playbook state catalog.
- Workflow state-binding role names are unique within a workflow entry.
- Relative workflow, profile, and state paths resolve deterministically from playbook-owned context.
- Launch-time input overrides, when supported, deterministically override workflow and profile input defaults for one run only.
- Workflow logical state roles resolve deterministically to declared playbook state entries.
- Every declared workflow logical state role has a binding in the active playbook workflow entry.
- No playbook workflow entry provides extra state bindings for undeclared workflow logical state roles.
- No silent fallback resolves a missing named workflow or profile to an arbitrary nearby file.
- Workflow business logic remains in workflow files rather than being duplicated as playbook-only execution semantics.

<!-- source: verification/workflow/authoring.md -->

# Workflow authoring verification

## Rule

Workflow and profile authoring must remain a first-class and agent-usable surface.

## Checks

- Public operations are discoverable enough for composition without reading connector implementation internals.
- Schema, examples, and runtime diagnostics are sufficient for iterative repair of an authored workflow.
- Routine project adaptation prefers composing workflows and profiles over introducing new connector semantics.
- Reusable included fragments remain understandable as a static-composition `include` surface even when they declare fragment-local `args`.
- Authoring verification should not require all reusable-fragment semantics to collapse into `include` when a later runtime-scoped invocation surface would be clearer.
- If a future `run` surface is introduced, authoring verification should preserve a short explainable distinction between static composition and runtime-scoped fragment invocation.
- A valid declaration is not treated as fully sufficient when it is opaque, shell-heavy, or difficult to review.

<!-- source: verification/workflow/guard-expressions.md -->

# Guard expression verification

## Rule

Guard expressions must improve policy readability without collapsing explainability or machine-checkability.

## Checks

- Common execution conditions can be written more compactly than equivalent shell guard logic.
- Common execution conditions do not require creating a new bespoke public probe name for every simple predicate.
- Zero-argument probe references remain readable without mandatory empty call syntax.
- Boolean combinations inside one expression remain structured enough for validation and explanation.
- Runtime diagnostics can identify at least the failing subcondition, the observed value when available, and whether failure came from boolean mismatch or probe evaluation failure.
- Validation rejects statically invalid field paths against documented probe outputs.
- Guard resolution rejects effectful `action` operations inside expressions.
- Repeated identical probe references inside one expression need not be evaluated redundantly.

<!-- source: verification/runtime/guard-evaluation.md -->

# Guard evaluation runtime verification

## Rule

Guard evaluation results must remain explainable as a machine-usable runtime surface.

## Checks

- A blocked result identifies the blocking guard item.
- A blocked result identifies the failing subcondition when available.
- Runtime output distinguishes boolean guard failure from probe evaluation failure.
- Guard-evaluation traces remain structured enough for `check`, `plan`, and `explain` to report consistent blocker identity.
- Reuse of repeated identical probe references inside one expression does not weaken explainability.

<!-- source: verification/runtime/introspection-drift.md -->

# Verification for introspection drift

## Rule

If a runtime-visible surface changes, the published introspection surface must change in the same work.

## Runtime-visible surface

At minimum this includes:

- root discovery surface;
- workflow contract surface;
- playbook contract surface;
- capability states exposed to tools;
- expression roots, filters, builtins, and allowed surfaces;
- public operation metadata exposed for machine-readable consumption.

## Source-of-truth rule

Introspection must be assembled from runtime-owned metadata or from canonical contract data owned by the runtime-facing product layer.

Prose documents must not be the source of truth for published introspection.

## Enforcement expectations

The project must verify, at minimum:

- published introspection is machine-readable;
- published introspection is versioned;
- covered runtime-visible surface changes fail verification when introspection is not updated;
- parity checks detect drift between runtime-owned metadata and published introspection output.

## Review rule

A change that widens, narrows, renames, removes, or reclassifies a covered runtime-visible surface is incomplete unless the corresponding introspection and verification updates are included in the same work.

<!-- source: verification/runtime/invariants.md -->

# Invariants

## Core invariants

- unknown fields fail validation
- unknown operations fail resolution
- workflow holds orchestration, not algorithmic implementation
- structured result is required
- `check`, `plan`, `execute`, and `explain` are baseline runtime modes
- blocked-before-execution is distinct from execution failure
- runtime explanation is a structured surface, not merely logs or tracebacks
- runtime remains analysis-first rather than execute-first
- runtime is usable as a machine-readable decision surface, not only as an execution entrypoint
- contract-level runtime structures are losslessly JSON-serializable
- runtime decision surfaces remain machine-readable without format-specific parsing beyond standard JSON data handling

## Drift rule

If a change breaks any invariant, `meta/` must be updated explicitly in the same work.

<!-- source: verification/meta/packs.md -->

# Pack verification

## Rule

Generated files under `meta/packs/` must never be edited by hand.

Regenerate packs with `python3 tools/build_domain_packs.py meta/domain-packs.toml`.

## Check mode

The pack builder must support a `--check` mode that fails when generated output differs from committed output.

Verification command:

`python3 tools/build_domain_packs.py meta/domain-packs.toml --check`
