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

Action contracts may also expose conservative observation-invalidation metadata for runtime `check` reasoning.

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

## Observation invalidation metadata

An effectful action may declare which probe-derived observation scopes it invalidates.

When such metadata is present, runtime may use it to reason conservatively about the stability limits of pre-execution knowledge during `check`.

If an effectful connector action does not declare narrower observation invalidation metadata, runtime should conservatively treat it as invalidating the full observation namespace of that connector family.

Why this matters:
- `check` should not over-trust probe observations across later effect boundaries;
- missing invalidation detail must weaken confidence rather than justify optimistic approval;
- connector authors may improve precision incrementally without requiring perfect metadata coverage before the mechanism is useful.

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
