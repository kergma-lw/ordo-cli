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
- A parameterized probe reference should prefer a compact meta-style call surface, for example `gh.issue(issue=inputs.issue).status`.
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
- Raw stdout/stderr, when produced by an implementation, must be treated as optional detail fields rather than the primary contract surface.

## Extension boundary

- The system must allow project-local extension without forking the global contract.
- Project-specific policy must compose over stable connector operations instead of mutating their meaning.

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

## Product boundary

- Core semantics must stay small and explainable.
- The format must prefer explicit fields over implicit behavior.
- Drift between docs, schema, examples, and runtime must be detectable.
- Workflow and profile authoring must remain easier and more common than connector authoring in early product stages.

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
- `explain` output should include useful next actions when the runtime can infer them safely.
- The explanation surface must remain stable enough for agent tooling to rely on status codes and categories.

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

Implications:
- a `probe` must return not only an outcome but also meaningful observations and diagnostics;
- an `action` must return not only an outcome but also an effect summary and diagnostics;
- raw stdout/stderr, when produced by an operation, are supplementary detail fields rather than the basis of the contract.

## Bootstrap

A connector may have shared bootstrap or shared context for the whole family.

Examples:
- `gh` checks binary availability, auth, and required scopes at the family level;
- `gh.issue.view` checks its own local contract;
- `shell` defines supported interpreter policy, while `shell.command` executes a concrete command.

## Publicness

`connectors/` is a public and stable layer.

Implications:
- connector and operation names matter;
- family-level semantics matter;
- the meaning of a same-named operation must not change silently.

## Fixed v0 connector domains

- `git.*`
- `gh.*`
- `shell.*`

## Possible future connector namespaces

- `run.*`
- `ansible.*`
- `fs.*`
- `obsidian.*`

## Local extension namespaces

- `local.*`
- `project.*`

<!-- source: domain/workflow.md -->

# Workflow domain

## Role of the workflow

The workflow answers the question:

> what to check, in what order, and which public operations to call.

It must not answer the question:

> how a transformation or integration algorithm is implemented internally.

## What is acceptable in a workflow

- guards;
- ordered steps;
- references to profiles;
- compact parameters;
- simple branching when it has clear semantics.

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
- can be moved across projects while preserving contracts.
- can be authored and iteratively repaired by a sufficiently capable agent using contract docs, examples, and structured diagnostics.

<!-- source: domain/runtime.md -->

# Runtime domain

## Baseline modes

### `check`

Checks guards and static prerequisites.
It must not execute effectful business steps.

### `plan`

Builds an explainable plan:
- what will be checked;
- which steps are expected;
- where execution is blocked.

### `execute`

Executes the workflow.

### `explain`

Returns an explanation of the runtime decision:
- why a guard failed;
- why a particular step or profile was chosen;
- which overrides are active.

## Why this matters

For agent-authored workflows, `execute` alone is not enough.

The runtime needs modes that:
- reduce risk;
- improve reviewability;
- provide machine-readable reasoning.

<!-- source: domain/policy.md -->

# Policy domain

## Guard

A guard is a precondition check evaluated as part of policy before effectful workflow steps.

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

<!-- source: domain/boundaries.md -->

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

<!-- source: adr/0004-guard-expressions-prefer-orthogonal-probes.md -->

# ADR 0004: guard expressions prefer orthogonal probes

## Context

Guard expressions exist so workflow policy can remain compact and visible in the declaration.

The current connector surface can drift toward specialized probe names that encode policy directly, for example by exposing many narrow predicates whose only purpose is to avoid writing a simple comparison in the workflow.

That drift weakens one of the main reasons guard expressions exist in the first place.

## Decision

Guard-expression design should prefer a minimal and orthogonal public probe surface.

Policy composition should primarily live in the workflow declaration through guard expressions rather than in a growing catalog of bespoke policy-encoded probe names.

Specialized probes may remain temporarily for migration or compatibility, but they are not the preferred long-term direction.

## Consequences

- Public probe contracts should expose stable output fields suitable for documented guard-expression field access.
- New connector work should avoid adding specialized policy probes unless a strong public-contract reason exists.
- Drift between meta examples and connector naming should be resolved by moving toward more orthogonal probe contracts rather than by normalizing policy sprawl into the connector layer.

<!-- source: model/workflow/entities.md -->

# Workflow entities

## Main entities

- `Workflow`
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

- A `Workflow` contains ordered `Guard` and `Step` entries.
- A `Guard` and a `Step` reference an `OperationRef`.
- A `Connector` groups operations and can own shared bootstrap/runtime prerequisites.
- A `Profile` supplies reusable parameters or composition defaults.
- An `Override` changes resolution explicitly, never silently.
- An `OperationContract` describes public inputs, outputs, effects, and failure modes.
- An `ExecutionPlan` describes checks, steps, and blockers without requiring effectful execution.
- An `OperationResult` captures structured connector-level outcome details.
- An `ExecutionResult` contains status plus diagnostics and outputs.

## Boundary reminder

- `Workflow`, `Guard`, and `Step` express orchestration intent.
- They do not own connector implementation algorithms.
- `Profile` and `Override` express composition and explicit local adaptation.
- `Diagnostic` and execution/result entities carry machine-usable analysis and runtime surfaces.

<!-- source: model/workflow/guard-expressions.md -->

# Guard expression model

## Concept

A guard expression is a boolean predicate evaluated during the guard phase.

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

## Output access semantics

- Field access after a probe reference means reading documented structured output from that probe result.
- Field access is not a general object method system.
- Public contract documentation must define which output fields are stable enough to reference from guard expressions.
- A boolean-valued field may be used directly as a condition.
- Non-boolean probe outputs should be compared through explicit documented field access such as `git.branch.value`.

## Guard list semantics

- A workflow may contain multiple guard items.
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
- `ordo.connectors` — public connector family implementations and registries.
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

## Explainability and failure normalization

Every operation must:
- return a structured result on both success and failure paths
- support narrow local explanation of its own outcome
- normalize internal exceptions into a structured failure result rather than escaping as the only observable surface

When an implementation produces raw stdout/stderr, those streams are secondary details inside the result contract, not the primary contract itself.

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

## Rule

Shared prerequisites should not be duplicated in every operation contract if they are already owned by connector bootstrap.

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
- `guards`
- `steps`

## Stable guard shape

```yaml
- uses: namespace.name
  with: {}
```

## Stable step shape

```yaml
- name: some-step
  uses: namespace.name
  with: {}
```

## Current rule

Unknown top-level and nested stable fields fail validation.

## Serialization rule

- Workflow files may be authored in YAML.
- Workflow semantics are defined over the loaded data model, not over YAML-specific syntax.
- Stable workflow data must be representable as a losslessly JSON-serializable structure after loading.
- YAML-specific mechanisms such as anchors, aliases, tags, or merge behavior must not introduce distinct runtime semantics unless explicitly standardized.

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
- gh.issue(issue=inputs.issue).project.member
- gh.issue(issue=inputs.issue).status not in ["Done", "In review"]
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

- guards are visible before steps run;
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

<!-- source: scenarios/authoring.md -->

# Authoring scenarios

## Human authoring

Human writes or reviews a workflow using readable connector operations, small schema surface, and examples.

Human should be able to answer, by reading the declaration:

- what policy is enforced;
- which guards can block execution;
- which steps are intended if guards pass;
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

<!-- source: verification/workflow/authoring.md -->

# Workflow authoring verification

## Rule

Workflow and profile authoring must remain a first-class and agent-usable surface.

## Checks

- Public operations are discoverable enough for composition without reading connector implementation internals.
- Schema, examples, and runtime diagnostics are sufficient for iterative repair of an authored workflow.
- Routine project adaptation prefers composing workflows and profiles over introducing new connector semantics.
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
