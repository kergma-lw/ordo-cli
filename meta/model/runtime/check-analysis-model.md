# Check analysis model exploration

## Status

This document is exploratory rather than normative.
It captures a possible internal runtime design direction for richer `check` behavior.
It does not by itself define the public contract.
Normative `check` rules live in `meta/model/runtime/check-semantics.md`.
Verification-oriented scenario hypotheses live in `meta/verification/runtime/check-mode.md`.
Conservative default invalidation behavior is also part of the connector contract in `meta/model/connector/contract.md`.
The more concrete preflight interpreter proposal lives in `meta/model/runtime/preflight-step-interpreter.md`.

## Why this document exists

`check` now has explicit normative requirements around pre-execution honesty, incomplete verdicts, guard coverage, and `pre_run` interaction.
Those requirements are necessary, but they do not yet determine one concrete internal runtime model.

This document exists to preserve a deeper line of reasoning before it disappears into ad hoc implementation work.
Its role is to capture:

- the design pressure behind richer `check` behavior;
- candidate internal structures that could support that behavior;
- candidate data that runtime may need to compute and retain;
- open questions that should remain visible during iteration.

This document is intentionally more speculative than the normative runtime docs.

## Problem statement

The baseline `check` contract sounds simple:

- answer whether execution may proceed safely;
- evaluate guard blocks and static prerequisites;
- avoid effectful business step execution.

In practice, that simple surface quickly runs into harder questions:

1. What does it mean for a verdict to be complete rather than partial?
2. When should runtime report `allowed`, `blocked`, or `unknown`?
3. How much guard evaluation should happen before execution?
4. How should runtime preserve workflow order and guard barriers while still performing aggressive preflight analysis?
5. How should playbook-owned `pre_run` orchestration affect the truth value and completeness of the main-workflow verdict?
6. How should runtime explain not only blockers, but also the limits of what it currently knows?

The purpose of this exploration is to keep those questions explicit and connected.

## Core working idea

One promising direction is to treat `check` not as a flat blocker scan, but as a structured preflight knowledge model.

In that direction, `check` would still emit a simple public verdict surface, but internally it would maintain a richer decision model that answers questions such as:

- which guards were relevant to the current verdict;
- which of those guards were actually evaluated;
- which were not yet evaluable and why;
- which observations were used to evaluate those guards;
- which later effectful steps would invalidate or weaken those observations;
- how strong the basis of the current verdict is.

This is not the same as simulating execution.
It is closer to reasoning about what runtime currently knows, what it does not know, and how stable that knowledge is within the pre-execution phase.

## Why this is not just a confidence score

It is tempting to describe richer `check` behavior as a kind of confidence score.
That language is useful up to a point, because the runtime does need some notion of stronger and weaker verdict basis.

However, a naked numeric score would be misleading if it hides the reasons behind that score.
The important design pressure is not primarily to produce a number.
It is to preserve structural reasons such as:

- relevant guards covered versus uncovered;
- known truths versus unknown truths;
- observations that are stable now versus observations that would be invalidated by certain step families;
- blocks whose executability is already grounded versus blocks whose status depends on later effectful outcomes.

If any summary confidence surface is added later, it should be derived from these structural reasons rather than replacing them.

## Snapshot-oriented interpretation of `check`

One useful framing is to treat `check` as operating over a pre-execution world snapshot.

That snapshot may include:

- workflow inputs;
- runtime state;
- active profile context;
- explicit overrides;
- read-only observations from public probes;
- playbook and workflow structure.

Within this framing, runtime may aggressively evaluate any guard whose truth value is determined by that current pre-execution knowledge surface.

This does **not** mean:

- assuming later effectful step outcomes;
- simulating business actions;
- pretending that future step-local data already exists;
- flattening the workflow into a structureless bag of policy checks.

Instead, it means being ambitious about what can be known from the current snapshot while remaining strict about what cannot.

## Why workflow structure must remain central

Even if runtime evaluates many guards from one snapshot, the workflow is still an ordered block structure.
The design must therefore preserve:

- guard barriers;
- later step sequences protected by those barriers;
- the order in which blocks matter to the workflow contract;
- the difference between guards that are already relevant to the current verdict and guards that belong to later structural regions.

This is important because `check`, `plan`, and `explain` all depend on more than a flat list of true and false conditions.
They depend on a decision model that can still answer:

- where execution is blocked;
- which steps are currently reachable;
- which later regions remain unresolved;
- why a guard matters to the current outcome rather than merely existing somewhere in the workflow.

## Candidate model: one structural decision tree or graph

The current exploration direction should not create a separate abstract “confidence tree” disconnected from workflow shape.
Instead, a better direction is to build one structural runtime decision model that mirrors workflow structure and carries analysis annotations.

The central recommendation of this document is therefore:

> Build one workflow-shaped preflight decision tree or graph, then store knowledge, coverage, and invalidation annotations on that structure and on the final verdict summary.

This keeps reasoning localized and explainable.

## Why a tree or graph rather than a flat list

A flat list of blockers is too weak for the kinds of questions that richer `check` behavior needs to answer.

For example, a flat list cannot easily preserve:

- whether a guard belonged to an early or late barrier;
- whether a step block became blocked because of policy or because analysis never reached a required precondition;
- whether an unknown result was caused by missing current knowledge or by dependence on future step outcomes;
- whether a later step would invalidate observations used by earlier guard evaluation.

A structured model allows runtime to keep these relationships explicit.

## Candidate node kinds

An implementation does not need all of these node kinds in its first version, but the following taxonomy is useful for thinking:

- `workflow` — the root node for one assembled workflow run surface;
- `block` — one ordered workflow block;
- `guard` — one guard item inside a guard block;
- `step` — one step item inside a step block;
- `observation` — one probe-derived fact used by one or more guards;
- `verdict` — the aggregated preflight result;
- `effect-domain` — an abstract domain that may be observed or invalidated.

For an MVP, a simpler model would likely be enough:

- workflow root;
- ordered block nodes;
- guard item nodes;
- step item nodes;
- verdict summary.

The richer observation and effect-domain nodes can begin as attached metadata rather than first-class graph nodes.

## Candidate annotations on guard nodes

Each guard node may need to retain more than its expression text or reference.
Useful annotations could include:

- `reference`;
- `block_index`;
- `relevant_now`;
- `evaluable_now`;
- `evaluated`;
- `result` with values such as `true`, `false`, or `unknown`;
- `unknown_reason`;
- `depends_on_future_step_outcome`;
- `depends_on_missing_step_local_data`;
- `observation_domains_used`;
- `input_dependencies`;
- `state_dependencies`;
- `probe_dependencies`.

The key point is not the exact field names.
The key point is that `check` needs a way to express not only a truth value, but why that truth value was or was not obtainable.

## Candidate annotations on step nodes

Step nodes do not exist in `check` merely as future execution placeholders.
They matter because they determine:

- which effect domains might be changed later;
- which barriers guard those later changes;
- where current observations would stop being stable;
- which later guards could depend on future outcomes.

Useful step annotations could include:

- `name`;
- `kind` such as `probe`, `action`, `run`, or `builtin`;
- `effect_domains`;
- `may_invalidate_domains`;
- `conditional`;
- `condition_expression`;
- `declared_effect_class`;
- `currently_reachable_if_prior_guards_pass`.

This is still preflight structure, not execution simulation.

## Candidate annotations on block nodes

Block-level annotations are useful because many runtime questions are really about barriers and transitions between barriers.

Useful block annotations could include:

- `type` such as `guards` or `steps`;
- `status` such as `ok`, `blocked`, `pending`, or `unknown`;
- `eligibility_now`;
- `covered_guard_count`;
- `uncovered_relevant_guard_count`;
- `unknown_guard_count`;
- `blocking_guard_references`;
- `depends_on_pre_run_outcome`;
- `future_dependent`.

These allow runtime to explain where one guard barrier ends and what remains unresolved beyond it.

## Candidate verdict-basis summary

The tree or graph should not be the only place where analysis knowledge is stored.
The final `check` result should also contain a compact verdict-basis summary derived from the structure.

Possible summary fields:

- `allowed_state` with values such as `allowed`, `blocked`, or `unknown`;
- `analysis_complete`;
- `relevant_guard_count`;
- `evaluated_relevant_guard_count`;
- `unevaluated_relevant_guard_count`;
- `blocking_guard_count`;
- `unknown_guard_count`;
- `incomplete_reasons`;
- `used_observation_domains`;
- `potential_invalidation_domains`;
- `coverage_strength` or `verdict_basis_strength`.

This summary exists for quick consumption by callers.
The tree or graph exists so that the summary remains explainable rather than magical.

## Observation domains and invalidation domains

One especially promising idea is to treat observations and planned effects in terms of coarse domains.

Examples:

- `git` domain for repository facts and git actions;
- `gh` domain for GitHub facts and GitHub actions;
- `state:<name>` domains for runtime-managed state locations;
- `shell:*` or similar broad domains for shell-based actions with large or uncertain effect surfaces.

This is useful because `check` often needs to answer not only “what is true now”, but also “how far should runtime trust this truth before later planned actions may invalidate it”.

The idea here is not to predict the exact future state of the world.
The idea is to model the *stability boundary* of current observations.

## Conservative influence modeling

If influence domains are introduced, they should begin conservatively.

For a first implementation, it may be enough to say things like:

- `git.*` actions invalidate `git` observations;
- `gh.*` actions invalidate `gh` observations;
- state-setting builtins invalidate the affected `state:<name>` observations;
- shell-like actions may invalidate many domains unless a narrower contract exists.

The purpose of this model is not to be omniscient.
Its purpose is to avoid over-trusting earlier observations after known effect boundaries.

When in doubt, the system should prefer reduced certainty over false precision.

## Relevance versus existence

One important design distinction is the difference between a guard that exists somewhere in the assembled workflow and a guard that is relevant to the current preflight verdict.

At least three categories are useful:

- `relevant_now` — this guard contributes directly to the current verdict surface;
- `not_yet_relevant` — this guard belongs to a structurally later region but does not yet constrain the current verdict;
- `relevant_but_not_evaluable` — this guard matters to the verdict, but runtime cannot yet honestly determine its truth from the current snapshot.

Without such a distinction, `check` risks either:

- becoming too shallow because it evaluates almost nothing;
- or becoming noisy and hard to interpret because it evaluates everything without telling callers what actually matters.

## `pre_run` as a first-class pressure case

Playbook-owned `pre_run` orchestration is a critical test case for this model.

Why:

- `pre_run` is structurally earlier than the main workflow;
- it may influence profile context, working directory, or other activation conditions;
- it can make the main workflow verdict partial rather than final;
- it exposes the difference between “no blocker seen yet” and “main workflow actually cleared”.

Any candidate analysis model that cannot represent this honestly is probably too weak.

This makes `pre_run` not just a corner case, but a useful forcing function.

## Candidate static check-expansion test for `run`

One especially useful next-step criterion is a narrow test for whether `check` may statically expand a `run` step into a subtree rather than treating it as an opaque barrier.

This is not yet intended as the full general semantics of `run`.
It is only a candidate admissibility test for static `check` expansion.

Runtime may treat a `run` step as check-expandable only when all of the following hold:

1. the target workflow or fragment is known statically;
2. the `run` arguments are resolvable from pre-execution knowledge;
3. the target workflow or fragment is statically loadable;
4. the target subtree is check-analyzable at the depth needed by the current verdict;
5. expanding the subtree does not require pretending that effectful execution has already happened.

Why this matters:

- this gives runtime a generic criterion that is broader than special-casing one current `pre_run` fragment;
- this keeps static `check` expansion tied to honesty rather than to convenience;
- this allows profile-only or other context-shaping `run` fragments to become analyzable without turning every `run` into an automatic inline expansion.

This test should be read conservatively.
Known arguments alone are not enough.
The point is not to expand every `run`, but to identify the subset that can be turned into a static `check` subtree without erasing the boundary between preflight analysis and effectful execution.

## Relationship to `plan` and `explain`

This exploration is about `check`, but it has direct consequences for `plan` and `explain`.

If runtime builds a richer structural preflight model, then:

- `plan` can inherit structural reachability and barrier information without inventing false certainty;
- `explain` can say not only why execution is blocked or allowed, but also why the current verdict remains partial;
- downstream modes can remain honest because they derive from a decision model that already preserves incompleteness.

This is one reason to prefer a shared internal model over mode-specific one-off logic.

## What this direction is **not**

It is important to state what this exploration does **not** propose.

It does not propose:

- running effectful business steps during `check`;
- silently converting `check` into a dry-run execution engine;
- predicting concrete future action success as if those actions had already run;
- replacing workflow structure with a purely probabilistic system;
- turning `check` into an opaque confidence number.

The proposal is about better preflight honesty, not hidden simulation.

## Suggested MVP shape

A first implementation does not need a full graph engine.

An MVP could keep the existing ordered block-oriented runtime shape and enrich it with additional annotations.

Minimum useful additions might include:

### Guard items

- whether the guard is relevant;
- whether it is evaluable now;
- whether it was evaluated;
- result value;
- unknown reason;
- observation domains used.

### Step items

- effect domains;
- may-invalidate domains;
- declared effect class.

### Verdict summary

- `analysis_complete`;
- `allowed_state`;
- `unevaluated_relevant_guards`;
- `incomplete_reasons`;
- a coarse `coverage_strength` or equivalent basis-strength field.

This would already be enough to prevent many falsely optimistic outcomes without overcommitting to a complex architecture.

## Questions that remain open

This exploration intentionally leaves several questions unresolved.

### 1. Public versus internal surface

How much of the richer analysis model should become public result payload, and how much should remain internal runtime machinery?

### 2. Domain metadata origin

Where should effect-domain or invalidation metadata live?
Possible homes include:

- connector contracts;
- operation publication metadata;
- runtime-side heuristics;
- a combination of explicit declarations and conservative fallback rules.

### 3. How strongly to distinguish relevance categories

Should runtime expose only a simple relevant/not-relevant split, or a richer distinction among relevant-now, later-relevant, and structurally present but verdict-irrelevant guards?

### 4. Summary vocabulary

Should the public surface say `confidence`, `coverage_strength`, `verdict_basis_strength`, `analysis_completeness`, or something else entirely?

The current document leans away from pure “confidence” language because it sounds probabilistic.

### 5. Treatment of shell-like actions

How broad should default invalidation be for shell-driven actions or launcher-mediated commands?

### 6. Relation to future `next` behavior

If runtime later offers richer next-safe-action behavior, should it derive directly from this same analysis structure?

The likely answer is yes, but this document does not attempt to settle that now.

## Design recommendation for now

Until a more concrete architecture is selected, the safest working recommendation is:

1. Keep `check` grounded in currently available pre-execution knowledge.
2. Preserve ordered workflow block structure in the internal decision model.
3. Track relevant guard coverage explicitly.
4. Represent incomplete verdicts explicitly.
5. Treat observation stability and invalidation as first-class analysis concerns.
6. Prefer structural reasons over opaque confidence numbers.

This recommendation is intentionally compatible with the normative `CHECK-MODE-*` rules while leaving implementation freedom.

## What a future ADR might decide

If this direction proves useful, a later ADR could settle questions such as:

- whether runtime should standardize effect domains across connectors;
- whether invalidation metadata belongs in connector publication surfaces;
- whether the internal model should remain a block list with annotations or become a more explicit graph;
- which summary fields become part of the stable public `check` result contract.

This document should therefore be read as a preserved exploration path, not as a frozen solution.
