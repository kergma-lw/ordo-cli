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
