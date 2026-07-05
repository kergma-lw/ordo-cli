# Runtime profile model

## Role

A profile is a named operational context for workflow activation.

Profiles belong to the runtime surface because they affect how one playbook run is activated and interpreted without changing workflow intent.

## What a profile may bind

A profile may bind runtime-facing context such as:

- workflow inputs;
- approved workflow-entry overrides;
- execution location such as a workflow-entry `working_directory` expression input;
- future execution modifiers such as named launchers or other runtime-scoped wrappers when standardized.

Profiles may therefore act as the project-local place where launcher-relevant context is selected, as long as launcher usage remains explicit and reviewable.

## What a profile is not

A profile is not:

- a separate workflow language;
- an implicit source of business policy;
- a hidden mutation layer that silently rewrites workflow meaning.

Profiles should select an operational context, not invent a second orchestration model.

## Activation semantics

One playbook run selects at most one active profile.

That active profile contributes runtime context before workflow execution begins.

The resulting run should remain explainable in terms of:

- which profile is active;
- which profile-provided inputs are in force;
- which approved overrides are active.

## Reviewability expectation

Profile-owned behavior must remain explicit and reviewable from playbook material.

If a profile changes execution-relevant context, the runtime explanation surface must be able to report that fact without requiring inspection of implementation internals.

## Relationship to workflow intent

Workflow files describe orchestration intent.

Profiles describe where and under which approved activation context that intent runs.

This separation allows the same workflow to remain reusable while still supporting project-specific operational contexts.
