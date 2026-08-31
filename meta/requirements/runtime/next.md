# Runtime requirements for `next`

## Role

- `next` must answer the continuation question "which workflow next?" for the current playbook context.
- The baseline public meaning of no-argument `next` is global to the visible workflow set, not limited to one already-selected workflow.
- `next` must not accept a workflow argument in its baseline public CLI form.
- `next` must stay non-effectful.

## Shared evidence basis

- `next` must reuse the same pre-execution analysis evidence family used by `check`, `plan`, and `explain` rather than inventing a separate opaque recommendation engine.
- `next` must reason from structured workflow facts such as guard outcomes, missing inputs, blocker categories, probe evaluability, active profile context, and runtime-known readiness.

## V1 scope without explicit relations

- V1 must not require explicit predecessor, recovery, or continuation declarations in workflow authoring.
- V1 should evaluate all workflows visible in the current playbook scope, with any ordinary profile or environment filtering that runtime can justify structurally.
- V1 may later incorporate explicit continuation relations as an augmentation layer, but lack of such relations must not block the baseline feature.

## Minimum candidate distinctions

- `next` should distinguish at least:
  - runnable now;
  - blocked but evaluable;
  - awaiting required input;
  - not fully evaluable because required read-only observations could not be established safely;
  - weak current-context match.
- Missing required inputs must not be collapsed into ordinary failed guards.
- Probe-evaluation inability must remain distinguishable from a negative guard verdict.

## Recommendation method for v1

- V1 should use an explainable weighted recommendation model over the current workflow set.
- The score inputs may include:
  - matched guard count;
  - matched guard ratio;
  - bonuses for exact readiness now;
  - bonuses for full evaluability;
  - penalties for hard blockers;
  - penalties for missing required inputs;
  - penalties for probe evaluation failure or other non-evaluable guard dependencies.
- Raw matched-guard ratio alone must not be treated as sufficient recommendation semantics.
- Outcome-driven boosts based on normalized blocker or failure categories may be added only when runtime can explain them in structured form.

## Result contract expectations

- `next` must return machine-readable output.
- The output should include at least:
  - one best candidate workflow when runtime can justify one;
  - nearby alternatives when they are materially competitive;
  - the classification of each returned candidate;
  - the main reasons and blockers that shaped the ranking;
  - explicit uncertainty when no strong recommendation can be made honestly.
- The result must help a human or agent answer:
  - why this workflow is suggested now;
  - why it ranked above nearby alternatives;
  - what blocker or missing input would change the recommendation.

## Safety and honesty

- `next` must prefer structural reasons over opaque confidence language.
- `next` must not present a weak or underspecified recommendation as if it were a fully justified ready-now answer.
- When no workflow can be recommended honestly, `next` should return uncertainty plus the strongest known blockers or missing-input requests rather than inventing a winner.
