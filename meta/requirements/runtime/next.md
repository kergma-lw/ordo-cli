# Runtime requirements for `next`

## Role

- `next` must answer the continuation question "which workflow next?" for the current playbook context.
- The baseline public meaning of no-argument `next` is global to the visible workflow set, not limited to one already-selected workflow.
- `next` must not accept a workflow argument in its baseline public CLI form.
- `next` must stay non-effectful.

## Shared evidence basis

- `next` must reuse the same pre-execution analysis evidence family used by `check`, `plan`, and `explain` rather than inventing a separate opaque recommendation engine.
- `next` must reason from structured workflow facts such as guard outcomes, missing inputs, blocker categories, probe evaluability, active profile context, and runtime-known readiness.
- `next` should also reuse structurally available state-topology evidence when workflows read, write, or delete runtime-managed state.

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
- V1 should preserve an explicit semantic precedence ladder before final numeric tie-breaking.
- At minimum, the recommendation order should distinguish:
  1. workflows connected to the active state-backed context versus unrelated utility workflows;
  2. workflows blocked only by execution-only input versus workflows blocked by context-bearing input;
  3. workflows blocked by world-state mismatch versus workflows whose world-state guards already fit;
  4. inspection-only workflows versus workflows that can continue, close, or establish work context.
- When active state clearly identifies a current work context, `next` should prefer state-connected candidates over unrelated ready-now utility workflows.
- Within one active state-connected context, a workflow blocked only by execution-only input should rank above a workflow that still depends on non-input world-state changes.
- The score inputs may include:
  - state-affinity bonuses for workflows that belong to the currently active state-backed context;
  - role-sensitive treatment for workflows that mainly inspect context versus workflows that continue or close it;
  - matched guard count;
  - matched guard ratio;
  - bonuses for exact readiness now;
  - bonuses for full evaluability;
  - penalties for hard blockers;
  - penalties for missing required inputs;
  - penalties for probe evaluation failure or other non-evaluable guard dependencies.
- Raw matched-guard ratio alone must not be treated as sufficient recommendation semantics.
- Outcome-driven boosts based on normalized blocker or failure categories may be added only when runtime can explain them in structured form.
- When state evidence is weak or absent, `next` should degrade gracefully toward the guard-driven baseline rather than pretending to know the current continuation cluster.

## Result contract expectations

- `next` must return machine-readable output.
- `next` retains its current recommendation and ranking evidence. The standalone `graph` command has a separate static possible-process purpose and versioned contract; see `graph.md`.
- The output should include at least:
  - one best candidate workflow when runtime can justify one;
  - nearby alternatives when they are materially competitive;
  - the classification of each returned candidate;
  - state-affinity or context-cluster evidence when that evidence materially shaped the ranking;
  - the main reasons and blockers that shaped the ranking;
  - explicit uncertainty when no strong recommendation can be made honestly.
- The result must help a human or agent answer:
  - why this workflow is suggested now;
  - why it ranked above nearby alternatives;
  - what blocker or missing input would change the recommendation.
- The human-readable text surface should include a compact explanation tag near each surfaced workflow so the recommendation does not look like an unexplained score dump.
- Standalone `graph` must not call next activation, explanation, or ranking. Changing graph output must not change next eligibility, ranking, behavior, or result shape.

## Safety and honesty

- `next` must prefer structural reasons over opaque confidence language.
- `next` must not present a weak or underspecified recommendation as if it were a fully justified ready-now answer.
- When no workflow can be recommended honestly, `next` should return uncertainty plus the strongest known blockers or missing-input requests rather than inventing a winner.
