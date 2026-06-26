# Authoring domain

## Role

Authoring is a first-class product surface.

Ordo is not only meant to execute workflows. It must also be understandable and writable by a sufficiently capable agent working from the documented contract surface.

## Primary extension path

The primary extension path in early Ordo is:

- compose workflows from existing public operations;
- compose profiles from explicit presets and policy choices;
- adapt projects through explicit declarative configuration.

The primary extension path is not:

- rapidly inventing new connector families;
- casually creating new operation semantics during routine workflow authoring.

## Discoverability

An author should be able to discover:

- which operations exist;
- what each operation means;
- what inputs and result shapes are expected;
- which examples and patterns are considered idiomatic.

## Checkability

Authoring must be checkable before execution.

An agent should be able to ask, in structured form:

- is this workflow valid;
- are all references resolvable;
- is execution likely blocked now;
- what should be changed to make the declaration better or safer.

## Quality expectation

Good authoring is more than schema validity.

It should preserve:

- explicit intent;
- visible policy;
- reviewability;
- stable public semantics;
- minimal dependence on hidden shell behavior.
