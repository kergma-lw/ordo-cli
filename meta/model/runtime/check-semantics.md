# Check mode semantics

## Role

`check` is the runtime's pre-execution verdict surface over currently available knowledge.
It exists to answer whether execution may proceed safely without executing effectful business steps.

`check` may share its underlying analysis basis with other mode projections such as `review`, but its published verdict must remain a runtime-executability answer rather than an authoring-quality score.

## CHECK-MODE-001 — Pre-execution verdict over currently available knowledge

`check` must report its verdict only over knowledge that is available before effectful step execution in the current run.

Why this matters:
- this keeps `check` honest about what it actually knows now rather than what later execution might reveal;
- this preserves the difference between preflight decision support and post-execution explanation;
- this prevents a false impression that `check` has already established facts that only later step outcomes could establish.

## CHECK-MODE-002 — No effectful business step execution

`check` must not execute effectful business steps in order to improve or complete its verdict.

Why this matters:
- a preflight mode that performs business effects is not safe to use routinely;
- users and agents must be able to call `check` without risk of hidden operational change;
- this keeps the semantic boundary between `check` and `execute` reviewable.

## CHECK-MODE-003 — Workflow order remains semantically binding

`check` must preserve the ordered workflow block structure in its decision model even when it evaluates many guards from one pre-execution world snapshot.

Why this matters:
- the workflow contract answers what to check and in what order;
- guard barriers must remain attributable to the later step sequences they protect;
- `plan` and `explain` depend on a decision model that still reflects block boundaries rather than only a flat verdict list.

## CHECK-MODE-004 — Relevant guard coverage is part of the contract

`check` must distinguish between guards that were relevant and actually evaluated, guards that were relevant but not yet evaluable, and guards that were outside the currently supported pre-execution decision surface.

Why this matters:
- a verdict is not trustworthy when runtime cannot say which relevant guards it actually covered;
- this gives both humans and agents a way to tell the difference between a clean preflight and a partial one;
- this prevents silent loss of policy coverage when workflow structure evolves.

## CHECK-MODE-005 — No observed blocker is not the same as execution allowed

`check` must not treat the absence of observed blockers as equivalent to an allowed verdict when relevant guard coverage is incomplete.

Why this matters:
- missing evidence is not positive evidence;
- otherwise runtime can report `allowed` simply because it never reached or evaluated the real blocking conditions;
- this is the core protection against falsely optimistic preflight results.

## CHECK-MODE-006 — Incomplete analysis must be representable explicitly

`check` must be able to report an incomplete or unknown verdict when it cannot honestly establish either allowed or blocked from currently available knowledge.

Why this matters:
- some workflows cannot be fully decided before later step outcomes exist;
- runtime needs a truthful middle state between clean approval and explicit refusal;
- downstream `plan`, `explain`, and agent logic need a stable way to handle partial preflight knowledge.

## CHECK-MODE-007 — Pre-execution guard evaluation may be aggressive within safe bounds

`check` may evaluate any guard whose truth value is determined by the current pre-execution world snapshot, workflow inputs, runtime state, profile context, overrides, and read-only probe observations, so long as no effectful business step execution is required.

Why this matters:
- this allows `check` to provide stronger safety value than a minimal first-block-only preflight;
- many workflows benefit from broad early blocker discovery even when later guarded steps are not yet executable;
- this keeps the mode useful without collapsing it into simulation or effectful dry-run behavior.

## CHECK-MODE-008 — Later step outcomes must not be smuggled into preflight truth

`check` must not claim to know the truth value of a guard when that truth depends on effectful step outcomes or step-local data that do not exist yet in the current pre-execution state.

Why this matters:
- this keeps `check` from pretending that future execution results are already available;
- this protects the boundary between policy evaluation and control flow that depends on step outcomes;
- this prevents fake completeness produced by hidden simulation assumptions.

## CHECK-MODE-009 — `pre_run` semantics must be explicit in the verdict model

When playbook-owned `pre_run` orchestration affects what `check` can know about the main workflow, runtime must represent that effect explicitly rather than silently treating the main workflow as already cleared.

Why this matters:
- playbook orchestration changes the reachable pre-execution decision surface;
- without an explicit rule here, runtime can report optimistic verdicts before main-workflow guards were actually covered;
- `plan` and `explain` need a stable basis for describing whether preflight knowledge is still partial because of `pre_run`.

## CHECK-MODE-010 — Downstream modes inherit check honesty, not just check data

Any richer mode that derives from `check` must preserve `check`'s distinction between allowed, blocked, and incomplete knowledge rather than upgrading incomplete preflight results into confident approval.

Why this matters:
- `plan` and `explain` become misleading if they narrate certainty on top of an incomplete verdict;
- users and agents should be able to trust that richer reasoning surfaces do not silently erase uncertainty;
- this keeps the shared internal decision model coherent across baseline modes.

## CHECK-MODE-011 — Observation invalidation must default conservatively

When runtime tracks action-driven invalidation of probe-derived observations during `check`, missing narrow invalidation metadata for an effectful connector action must not strengthen the verdict basis; runtime should conservatively fall back to the full observation namespace of that connector family.

Why this matters:
- `check` needs a safe default when action contracts do not yet publish precise invalidation detail;
- a missing annotation should reduce precision rather than create false stability claims;
- this allows incremental adoption of invalidation metadata without weakening preflight honesty.

## CHECK-MODE-012 — Step-derived read-only knowledge may strengthen preflight analysis

`check` may use step-derived read-only knowledge when that knowledge is produced through the runtime-owned preflight step interpreter defined in `meta/model/runtime/preflight-step-interpreter.md`.
Such interpretation must remain non-effectful, ordered, conservative, and explicit about halt reasons.

Why this matters:
- relevant read-only observations may live behind step flow rather than direct guard probes;
- runtime should be able to strengthen guard coverage without turning `check` into hidden execution;
- when a nested read-only observation fails, `check` should preserve the underlying probe diagnostics so authors can see the root cause without extra reconstruction work;
- a dedicated contract keeps richer preflight behavior reviewable.

## CHECK-MODE-013 — Advisory preflight-observation metadata may strengthen explainability without becoming a prerequisite

When an effectful action declares advisory preflight-observation templates, runtime may use them to evaluate how well the workflow's current pre-execution basis supports explanation of that step's applicability and expected effect.

Missing advisory observations must not by themselves make the workflow inapplicable.
They may weaken preflight-support quality, explanation strength, or authoring guidance, but they must not silently become hidden executability rules.

Why this matters:
- some actions remain semantically clear while still benefiting from richer preflight observation basis;
- runtime needs a way to distinguish execution validity from explanation strength;
- advisory templates allow connector families to help `check`, `plan`, and `explain` without moving workflow-policy logic into connector actions.

## CHECK-MODE-014 — Author-facing recommendations should preserve workflow expression shape when possible

When runtime renders a recommended preflight observation from action metadata, it should prefer the workflow expressions that currently supply the referenced action arguments rather than only the resolved runtime values.

Why this matters:
- author-facing recommendations are more useful when they resemble the workflow that must be edited;
- expression-shaped guidance remains stable across runs better than one-shot resolved values;
- this keeps long or awkward rendered expressions attributable to workflow authoring quality rather than pushing beautification burden into `check`.

## CHECK-MODE-015 — Recommended-observation matching must stay exact and structural

When runtime compares advisory preflight-observation templates against observations already established by the workflow, that comparison must remain deterministic and structural.

Covered means runtime can prove the same canonical probe reference, the same relevant field selection when applicable, and the same action-argument-relative workflow expressions after rendering.
Runtime must not use heuristic near-matching, guessed semantic equivalence, or value-level similarity to claim that a recommendation is already covered.

Why this matters:
- deterministic matching keeps `check` predictable for humans and agents;
- exact structural comparison avoids false positives that would hide genuinely missing observations;
- workflows that want readable stable matching can introduce early `let` bindings rather than relying on runtime guesswork.
