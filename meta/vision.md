# Vision

## In short

Ordo is a local declarative ritual engine.

It exists to describe operational workflows in a form that:
- a human can read and review;
- an agent can author and validate;
- the runtime can execute deterministically;
- a project can extend locally without forking the entire system.

One of the core qualities of the product is that a sufficiently capable agent can learn how to compose workflows and profiles from the documented contract surface and then check whether the authored result is valid and meaningful.

## What problem this solves

The problem is not the absence of shell, but that shell expresses these things poorly:
- policy;
- guardrails;
- explainability;
- stable machine-readable contract;
- composition of shared and local operations.

## What counts as a good outcome

A good Ordo workflow is:
- short;
- explainable;
- not hiding critical semantics in shell strings;
- portable across projects while preserving public connectors and operations;
- open to local extension without silently changing meaning.

## What the project is not trying to do

Ordo should not immediately become:
- a generic CI platform;
- a distributed workflow engine;
- a replacement for Python as a language;
- a giant YAML DSL with full programmability.

Focus: local workflows + public connectors + strong validation.

Early product focus also favors agent-authorable workflows and profiles over fast connector invention.
