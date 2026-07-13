# Runtime profile model

## Role

A profile is a named operational context for workflow activation.

Profiles belong to the runtime surface because they affect how one playbook run is activated and interpreted without changing workflow intent.

## What a profile may bind

A profile may bind runtime-facing context such as:

- workflow inputs;
- approved workflow-entry overrides;
- a profile-scoped execution `working_directory` default;
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
- whether the active profile came from explicit caller choice or playbook defaults;
- which profile-provided inputs are in force;
- whether the profile selected the effective execution working directory or yielded to a more specific workflow-entry declaration;
- which approved overrides are active.

## Runtime profile switching

Runtime profile switching belongs to engine semantics rather than to ordinary connector integration semantics.

The public construct for this should be `profile_switch`.

`profile_switch` should:

- name the target profile explicitly;
- behave as a runtime context transition for subsequent steps or nested workflow execution within the current run;
- apply the target profile's missing-input defaults to subsequent steps without overriding explicit activation inputs already in force;
- avoid silently re-activating already-executed workflow material under a different profile;
- remain explainable in structured runtime outputs;
- depend only on pre-execution knowledge such as `inputs.*`, `state.*`, literals, or equivalent runtime-static context;
- reject `step.*` dependencies.

Because `profile_switch` is runtime-owned context shaping rather than an ordinary business-world action, `check` may treat deterministic profile switches as static context annotations inside its decision tree rather than as opaque effect barriers.

## Reviewability expectation

Profile-owned behavior must remain explicit and reviewable from playbook material.

If a profile changes execution-relevant context, the runtime explanation surface must be able to report that fact without requiring inspection of implementation internals.

## Relationship to workflow intent

Workflow files describe orchestration intent.

Profiles describe where and under which approved activation context that intent runs.

This separation allows the same workflow to remain reusable while still supporting project-specific operational contexts.
