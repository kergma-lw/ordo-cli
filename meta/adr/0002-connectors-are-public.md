# ADR 0002: connectors are public

## Decision

`connectors/` is a public contract layer.

## Why

Workflow portability and explainability depend on stable connector and operation semantics.

## Consequence

Silent same-name semantic shadowing must not be the default behavior.
