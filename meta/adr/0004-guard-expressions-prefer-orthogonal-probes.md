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
