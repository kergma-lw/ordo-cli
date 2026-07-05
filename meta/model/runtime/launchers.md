# Runtime launcher model

## Role

A launcher is a named execution wrapper that may be selected explicitly for a step.

Launchers exist to support rare execution environments for shell-like steps without turning workflow authoring into a language-specific connector matrix.

## Why launchers exist

Some project-local commands require an execution wrapper such as:

- entering a repository-selected Node environment;
- activating a Python virtual environment;
- invoking a project-specific toolchain bootstrap that is unknown to the runtime core.

Those concerns are execution concerns, not domain operations.

## Scope

Launchers should be attached only to steps that explicitly request them.

They should not be treated as an implicit wrapper around every connector operation in a workflow run.

In particular:

- `git.*` and `gh.*` operations should remain unaffected unless a future model explicitly says otherwise;
- launcher behavior should target shell-like execution surfaces rather than broad connector families by default.

## Shape expectations

The initial launcher model should remain intentionally small.

A launcher definition may declare:

- which execution surface it wraps;
- an optional entry wrapper or prelude;
- an optional exit wrapper or cleanup phase.

A step may then select a launcher explicitly.

## Reviewability

Launcher usage must remain visible in playbook material and explainable in runtime outputs.

The model should avoid hidden launcher auto-selection based on command text heuristics.

## Constraints

Launchers are an exception path for rare toolchain wrappers.

If most workflow steps require launchers, that is a signal that runtime primitives or project-local operations are missing.
