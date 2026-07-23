# Preflight step interpreter

## Status

This document is normative for the runtime-facing contract of preflight step interpretation.
It defines the required boundary, invariants, and minimum explanation surface for using step-derived read-only knowledge inside `check`.
Normative mode-level `check` rules continue to live in `meta/model/runtime/check-semantics.md`.

## Role

The proposed preflight step interpreter is a runtime-owned analysis layer inside `check`.
Its role is to derive additional pre-execution knowledge from workflow step flow without executing effectful business steps.

## Problem

`check` already supports direct guard evaluation over pre-execution knowledge.
It is less effective when relevant read-only observations are only reachable through step flow such as:

- `probe` steps;
- `value` steps;
- `register` bindings;
- `if` conditions over already-known values;
- nested `run` fragments that remain preflight-analyzable.

This creates an avoidable gap between:

- what runtime can already describe in `plan`; and
- what runtime can honestly use to strengthen guard coverage in `check`.

## Contract

- The interpreter is part of `check`, not a hidden `execute` variant.
- The interpreter may evaluate only `read_only` and `analysis_safe` steps.
- The interpreter may derive step-local knowledge and feed that knowledge back into guard coverage.
- The interpreter must stop before any effectful business step.
- The interpreter must preserve the same honesty rules as `check` for `allowed`, `blocked`, and `unknown` verdicts.

## Scope boundary

Allowed step kinds and capabilities:

- read-only probe steps;
- pure `value` evaluation;
- `register` materialization;
- `if` evaluation when all dependencies are already known;
- nested `run` expansion when the callee remains preflight-analyzable;
- future bounded `run` fan-out when the array source, whole-step eligibility, and callee analyzability remain preflight-computable;
- deterministic runtime context shaping already allowed by `check` semantics.

Disallowed step kinds and capabilities:

- effectful connector actions;
- `state_set`;
- `state_delete`;
- any step whose inputs depend on unknown values;
- any branch whose condition truth value is not yet known;
- any nested run that requires effectful execution or unknown step-local data.
- any bounded `run` fan-out whose source cardinality or callee analyzability cannot be established well enough for the current preflight phase.

## PREFLIGHT-STEP-001 — Step interpretation remains strictly non-effectful

The preflight interpreter must never execute an effectful business step.

Why this matters:
- `check` must remain safe to call routinely;
- step-derived knowledge must not blur into hidden execution;
- richer preflight analysis must not weaken the core runtime safety boundary.

## PREFLIGHT-STEP-002 — Step-derived knowledge stays inside pre-execution truth

The preflight interpreter may derive knowledge only from currently available pre-execution sources and already interpreted read-only step results.
It must not assume future effectful outcomes, unavailable `step.*.outputs`, or mutations that have not happened.

Why this matters:
- the interpreter exists to strengthen current knowledge, not to predict execution;
- otherwise `check` could silently upgrade unknown conditions into false certainty;
- plan and explain surfaces depend on the same honest boundary.

## PREFLIGHT-STEP-003 — Classification is explicit and conservative

The runtime must classify steps for preflight purposes using a contract-backed, runtime-visible scheme.
When classification metadata is missing or insufficient, the runtime must reduce precision rather than upgrading the step to analyzable.

Why this matters:
- preflight interpretation must not depend on hidden heuristics that callers cannot reason about;
- missing metadata should produce conservative incompleteness rather than optimistic analysis;
- implementation work needs a stable public vocabulary for explainability and verification.

## PREFLIGHT-STEP-004 — Ordered step dataflow remains semantically binding

The interpreter must respect declared step order, `register` materialization, and step-local dependencies when deriving preflight knowledge.
It must not flatten a step block into an unordered bag of probes.

Why this matters:
- later read-only steps may depend on earlier derived values;
- branch reachability and stop reasons depend on dataflow, not just step presence;
- callers need explanations that match authored workflow order.

## PREFLIGHT-STEP-005 — Stop reasons are first-class runtime outputs

When the interpreter cannot continue an analyzable path, it must preserve prior knowledge and emit a machine-readable halt reason tied to the blocked step or branch.

Why this matters:
- partial knowledge should remain useful even when a later path becomes unknown;
- runtime must be able to explain why coverage stopped growing;
- downstream verdicts need a stable basis for incomplete analysis.

## PREFLIGHT-STEP-006 — Step-derived knowledge must integrate with guard coverage honestly

Knowledge produced by the preflight interpreter must feed into the same preflight decision model used by `check`, `plan`, and `explain`.
It must not upgrade incomplete relevant coverage into an `allowed` verdict.

Why this matters:
- richer preflight logic is valuable only if it improves the actual runtime verdict basis;
- downstream modes should inherit stronger evidence without erasing uncertainty;
- one shared decision model keeps runtime reasoning coherent.

## Hard invariants

- `check` must never execute an effectful business step.
- Unknown values must never be upgraded into known values by heuristic guessing.
- Missing metadata must weaken precision rather than strengthen verdicts.
- Any derived fact must remain attributable to its source input, state binding, value step, probe, or nested run.
- Any analysis stop must be recorded as structured incompleteness rather than collapsed into silence.
- Incomplete relevant coverage must continue to prevent `allowed` verdicts.

## Knowledge sources

The interpreter may read from:

- workflow inputs;
- runtime state;
- active profile context and overrides;
- literals and pure local-expression outputs;
- outputs of previously interpreted read-only steps;
- outputs of read-only probes;
- already-expanded nested preflight results.

The interpreter may not assume:

- future effectful outcomes;
- unavailable `step.*.outputs` values;
- branch results whose conditions have not been computed;
- state mutations that have not happened.

## Step classification contract

The runtime must classify steps into at least these categories:

- `read_only_analyzable`;
- `read_only_unanalyzable`;
- `effectful`;
- `context_only`;
- `unknown`.

This classification must be runtime-visible and contract-backed rather than heuristic-only.

## Evaluation model

- Interpret step blocks in declared order.
- Materialize `register` outputs for successful read-only steps.
- Evaluate `if` only from currently available knowledge.
- Skip branches whose `if` evaluates to `false`.
- Halt the current analyzable path when the next required step is effectful, unknown, or not yet computable.
- Preserve all knowledge collected before the halt.

## Stop model

The interpreter must stop a path when it encounters:

- an effectful step;
- an unknown step classification;
- an unresolved step argument;
- an `if` condition that depends on unknown data;
- a `step.*.outputs` dependency that has not been produced;
- a nested run that is not preflight-analyzable.

Each stop must emit a machine-readable reason and the exact blocked step or branch.

## Integration with `check`

- Direct guard evaluation and step-derived read-only knowledge must contribute to one preflight decision model.
- Guard coverage must distinguish:
  - directly evaluated guards;
  - guards closed by interpreter-derived observations;
  - guards still relevant but not yet evaluable.
- `allowed_state`, `analysis_complete`, `incomplete_reasons`, `guard_coverage`, and block-level status must reflect both sources of knowledge.
- `plan` and `explain` must inherit the improved preflight basis without upgrading incomplete knowledge to false certainty.

## Public explanation surface

The interpreter should produce structured outputs such as:

- `preflight_step_items`;
- `preflight_observations`;
- `preflight_halts`;
- `knowledge_sources`.

Each interpreted step item should expose at least:

- step name;
- kind/classification;
- status;
- whether it was reached;
- whether it was interpreted;
- any registered outputs retained for later reasoning;
- halt or skip reason when applicable.

## Composition with nested `run`

- Nested runs should remain caller-visible in the preflight surface.
- Nested results should preserve origin boundaries such as caller step and callee workflow.
- Callee-derived knowledge may flow back to the caller only through structured preflight outputs.
- Nested effectful or unanalyzable regions must stop analysis conservatively rather than silently flattening into success.

## Planned composition with bounded `for_each`

If `run` later gains bounded `for_each`, the preflight surface should preserve one explicit fan-out run node with its own cardinality and eligibility annotations rather than pretending the repeated calls never existed.

- Whole-step `if` still applies to the fan-out step as one unit.
- Preflight may record exact item count when the array source is statically known.
- When the array source is not statically known, preflight should record runtime-only cardinality rather than inventing a guessed count.
- Lexical nested fan-out in one authoring surface should remain invalid and therefore does not require a nested fan-out tree shape.

## Determinism and conservatism

- The same workflow plus the same pre-execution knowledge snapshot must yield the same preflight result.
- When the runtime cannot prove a read-only path is analyzable, it must mark the path incomplete rather than speculate.
- Missing narrow metadata must reduce precision, not increase confidence.

## Suggested implementation stages

1. Interpret pure `value` steps, read-only probes, and `register` chains without branch logic.
2. Add `if` evaluation over already-known values.
3. Add nested analyzable `run` interpretation with structured provenance.
4. Merge interpreter-derived knowledge into guard coverage and explanation surfaces.
5. Add targeted verification for incomplete-path honesty and stop-reason explainability.

## Acceptance direction

The proposal is successful only if it:

- reduces avoidable `unknown` preflight verdicts;
- strengthens guard coverage using genuinely available read-only knowledge;
- preserves `check` as strictly non-effectful;
- keeps the result surface explainable without log scraping;
- avoids turning `check` into a disguised `execute` or broad dry-run simulator.
