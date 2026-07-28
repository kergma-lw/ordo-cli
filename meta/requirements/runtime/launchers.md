# Runtime launcher requirements

## Purpose

- Launchers are deprecated as a primary authoring path.
- The runtime may support named launchers for rare shell-like execution wrappers.
- A launcher must be an explicit execution concern rather than a business-domain operation.
- Launcher use must remain opt-in at the step level unless a future model standardizes a broader scope explicitly.

## Reviewability

- Launcher selection must be visible in playbook material.
- Runtime-facing outputs should be able to report which launcher, if any, was selected for a step.
- Launcher behavior must not depend on undocumented command-prefix heuristics.

## Boundaries

- Launchers must not become a substitute for missing domain operations.
- Launchers must not become a substitute for published project-local routines.
- The runtime should not require language-specific built-in connectors merely to enter project-local toolchains.
- A launcher should affect only the execution surface it is designed to wrap.

## Design guidance

- Prefer published routines over launchers for project-local automation that can be named, reviewed, and registry-backed.
- Prefer explicit launcher selection on rare shell-like steps.
- Prefer launchers over global shell setup when only a few steps need toolchain wrapping.
- Treat heavy launcher usage as a signal to improve runtime primitives or introduce clearer project-local operations.

## Deprecation guidance

- New playbook and workflow authoring should prefer routines or richer connector semantics over launcher-mediated shell execution.
- Launcher retention is primarily for compatibility with existing examples, tests, and legacy shell-like wrappers until a later removal decision is taken.
