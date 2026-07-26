# Check mode verification hypotheses

## Role

This document records verification-oriented hypotheses and scenario expectations for `check`.
It is not the normative source of `check` semantics.

Normative requirements live in `meta/model/runtime/check-semantics.md`.
Exploratory internal-model discussion lives in `meta/model/runtime/check-analysis-model.md`.

The purpose of this document is to preserve concrete checks that future implementation and test work should validate.

## HYP-CHECK-001 — Incomplete relevant guard coverage must block optimistic approval

Related normative rules:
- `CHECK-MODE-004`
- `CHECK-MODE-005`
- `CHECK-MODE-006`
- `CHECK-MODE-009`

Scenario shape:
- a playbook or workflow structure places `pre_run` or some other structurally earlier step region before main-workflow guards;
- the runtime does not actually evaluate one or more relevant main-workflow guards;
- no explicit blocking guard has yet been observed.

Expected result:
- `check` must not report a clean allowed verdict;
- the result must contain an explicit incomplete or unknown signal;
- the result should indicate that relevant guard coverage is incomplete rather than pretending that main-workflow policy has cleared.

Why this matters:
- this is the clearest protection against falsely optimistic preflight results;
- it verifies that runtime distinguishes “no blocker found yet” from “workflow is cleared to run”;
- it directly exercises the pressure case introduced by `pre_run`.

Failure meaning:
- a failure here means runtime is upgrading missing coverage into positive approval;
- downstream `plan` and `explain` will likely inherit misleading certainty from the same defect.

## HYP-CHECK-002 — Guard coverage must be represented structurally, not only as blockers

Related normative rules:
- `CHECK-MODE-004`
- `CHECK-MODE-006`
- `CHECK-MODE-010`

Scenario shape:
- a workflow contains several relevant guards;
- at least one relevant guard evaluates true;
- at least one relevant guard evaluates false;
- at least one relevant guard remains unevaluable from current pre-execution knowledge.

Expected result:
- `check` should distinguish these categories explicitly rather than collapsing everything into a blocker list;
- the runtime result should make it possible to tell which relevant guards were evaluated and which were not;
- an unknown or incomplete region should remain visible even if a different guard already failed.

Why this matters:
- the quality of a preflight result depends not only on blockers but on coverage transparency;
- both human readers and agents need to tell whether a verdict is fully grounded or only partially grounded;
- this prevents a false appearance of completeness when some policy surface was never actually checked.

Failure meaning:
- a failure here means runtime is hiding important coverage distinctions;
- later explanation quality will degrade because `explain` cannot narrate distinctions that `check` discarded.

## HYP-CHECK-003 — Aggressive preflight guard evaluation is allowed within current snapshot bounds

Related normative rules:
- `CHECK-MODE-001`
- `CHECK-MODE-003`
- `CHECK-MODE-007`

Scenario shape:
- a workflow contains later guard regions beyond the first immediate barrier;
- those later guards depend only on current inputs, runtime state, profile context, overrides, and read-only probe observations;
- no later guard in this scenario depends on future effectful step outcomes.

Expected result:
- runtime may evaluate those later guards during `check`;
- the result must still preserve block structure and guard attribution rather than flattening the workflow into one verdict list;
- any such additional evaluation should strengthen preflight knowledge without pretending that later effectful steps have already run.

Why this matters:
- this verifies that `check` can be meaningfully strong rather than stopping at the first narrow barrier by habit;
- it allows earlier discovery of blockers when those blockers are already decidable from the current snapshot;
- it protects against the opposite failure mode where `check` becomes too weak to be useful.

Failure meaning:
- a failure here means runtime is unnecessarily shallow even when more knowledge is safely available;
- this would undercut one of the main reasons to enrich `check` at all.

## HYP-CHECK-004 — Future-step-dependent guards must remain unknown rather than guessed

Related normative rules:
- `CHECK-MODE-001`
- `CHECK-MODE-006`
- `CHECK-MODE-008`

Scenario shape:
- a later guard depends on an effectful step outcome, a step-local output, or some other future execution product that does not yet exist in the pre-execution state.

Expected result:
- `check` must not invent a truth value for that guard;
- the runtime result should mark the guard as unknown, incomplete, or not yet evaluable;
- the result should preserve the reason that this guard depends on future execution knowledge.

Why this matters:
- this preserves the boundary between preflight analysis and actual execution;
- it prevents `check` from silently turning into speculative simulation;
- it ensures that later richer modes inherit honest uncertainty rather than fabricated certainty.

Failure meaning:
- a failure here means runtime is smuggling future execution assumptions into present knowledge;
- once that happens, the trustworthiness of `check` collapses even if the surface still looks structured.

## HYP-CHECK-005 — Observation invalidation should weaken verdict basis conservatively

Related normative rules:
- `CHECK-MODE-001`
- `CHECK-MODE-003`
- `CHECK-MODE-007`
- `CHECK-MODE-010`

Scenario shape:
- one or more guards are evaluated from current probe observations in some domain such as `git`;
- later planned steps belong to effect domains that may invalidate those observations, such as `git.*` actions or broad shell-like actions.

Expected result:
- `check` may still report what is currently true from the present snapshot;
- however, the runtime result should preserve that these observations sit before a potential invalidation boundary;
- if the implementation exposes verdict-basis or coverage-strength metadata, that metadata should reflect reduced certainty or reduced downstream stability rather than ignoring the invalidation risk.

Why this matters:
- this is the bridge between simple guard truth evaluation and richer preflight honesty;
- it gives runtime a way to preserve structural reasons for weaker verdict basis without faking future outcomes;
- it supports stronger later `plan` and `explain` behavior by making observation boundaries explicit.

Failure meaning:
- a failure here means runtime is treating all observations as equally stable even when later effect surfaces obviously threaten them;
- the result may still look correct in narrow cases while remaining conceptually unsafe in more complex workflows.

## HYP-CHECK-006 — Missing narrow invalidation metadata must fall back conservatively

Related normative rules:
- `CHECK-MODE-011`

Scenario shape:
- an effectful connector action appears in the workflow;
- runtime tracks observation invalidation during `check`;
- that action does not declare narrower invalidation metadata.

Expected result:
- runtime should not treat the action as preserving prior observations by default;
- runtime should conservatively fall back to invalidating the full observation namespace of that connector family;
- any verdict-basis reasoning should therefore become weaker rather than stronger in the face of missing narrow metadata.

Why this matters:
- a safe default is necessary if invalidation metadata is adopted incrementally;
- otherwise missing metadata would silently behave like proof of stability;
- this preserves honesty while allowing connector contracts to become more precise over time.

Failure meaning:
- a failure here means the system is optimistic exactly where it should be conservative;
- partial metadata rollout would then make `check` less trustworthy instead of more useful.

## HYP-CHECK-007 — Missing advisory preflight observations should weaken explanation quality without becoming blockers

Related normative rules:
- `CHECK-MODE-013`

Scenario shape:
- an effectful action appears in the workflow;
- that action declares advisory preflight-observation templates;
- the workflow does not currently establish one or more equivalent observations before the step.

Expected result:
- `check` should be able to report weaker or partial preflight support for that step;
- `check` must not upgrade the missing advisory observation into an executability failure by itself;
- any author-facing guidance should identify which recommended observation shape is absent.

Why this matters:
- the point of advisory metadata is to strengthen explanation quality without creating hidden prerequisites;
- otherwise connector-authored hints would silently become policy gates;
- both humans and agents need to distinguish inapplicability from weak preflight support.

Failure meaning:
- a failure here means advisory metadata has leaked into executability semantics;
- authors and agents would lose trust in `check` because suggestions would behave like undocumented blockers.

## HYP-CHECK-008 — Rendered recommendations should prefer workflow expressions over one-shot values

Related normative rules:
- `CHECK-MODE-014`

Scenario shape:
- an effectful step argument is supplied through a workflow expression such as `inputs.foo`, `state.bar`, or an early `let` binding;
- the action metadata declares a recommended preflight-observation template that references that action argument.

Expected result:
- when `check` renders author-facing guidance, it should prefer the workflow expression currently supplying that action argument;
- if no such expression is available, a fallback surface may still be shown, but expression-shaped guidance is preferred.

Why this matters:
- recommendations are more actionable when they resemble the authored workflow structure;
- long rendered expressions remain an authoring-quality signal rather than a reason for runtime to invent prettier names;
- agents can repair workflows more directly when recommendations are phrased in workflow terms.

Failure meaning:
- a failure here means `check` guidance is less actionable than it could be;
- the system would push users toward ephemeral run-instance values instead of durable workflow structure.

## HYP-CHECK-009 — Recommended-observation coverage must not rely on heuristic equivalence

Related normative rules:
- `CHECK-MODE-015`

Scenario shape:
- an action declares a recommended preflight-observation template;
- the workflow has already established a similar-looking observation before that step;
- the two observation shapes differ by argument expression, selected field path, or canonical probe form.

Expected result:
- `check` must treat the recommendation as covered only when the canonical shapes match exactly after rendering action-argument expressions;
- `check` must not mark the recommendation as covered because the values happen to look equal in one run or because the expressions appear semantically close;
- if exact structural matching is unavailable, `check` should leave the recommendation missing or unknown rather than guessing.

Why this matters:
- deterministic exact matching is more trustworthy than clever-looking heuristics in a structured workflow system;
- false-positive coverage would make `check` hide missing observations precisely where author guidance is needed most;
- this keeps the burden of naming or normalizing important expressions in workflow authoring rather than in speculative runtime inference.

Failure meaning:
- a failure here means `check` has started inventing equivalence classes it cannot actually prove;
- recommendation coverage would then become surprising, unstable, and hard to debug.
