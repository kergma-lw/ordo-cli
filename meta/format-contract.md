# Format contract

## Base shape

The minimal workflow describes:
- `version`
- `workflow`
- `inputs`
- `guards`
- `steps`

Project-local launch context such as named workflow catalog, named profile catalog, and runtime state declarations belongs to the playbook contract rather than to the minimal workflow contract.

## Invariants

- unknown fields fail validation;
- unknown connector operation references fail resolution;
- `steps` order is meaningful;
- `guards` are semantically evaluated before effectful steps;
- the schema must remain suitable for both human and agent authoring.

## Format principles

- minimal magic;
- explicit > implicit;
- a small set of connector families and operations is better than a broad but fuzzy model;
- every field must have clear runtime semantics;
- if the semantics cannot be explained briefly, they are probably too complex for the format.

## Serialization model

- workflow source may be authored in YAML;
- YAML is an authoring surface, not the canonical runtime model;
- after loading, workflow data must be representable as a losslessly JSON-serializable structure;
- canonical runtime-facing structures are JSON-shaped rather than YAML-shaped;
- authoring convenience must not introduce YAML-only semantics into runtime behavior.

## What should not be stabilized too early

- expression language;
- loops;
- retries;
- cross-step mutation model;
- ad-hoc templating rules.

A small valid core is needed first.
