# Playbook domain

## Role of the playbook

The playbook answers the question:

> which workflows are available in this project, under which names, with which project-local launch context.

It must not answer the question:

> what business steps a workflow performs internally.

## What a playbook owns

- project-local workflow catalog;
- named profile catalog for playbook-run profile selection;
- named runtime state declarations shared across project workflows;
- bindings from workflow-level logical state roles to concrete project state declarations;
- explicit execution working directory defaults and overrides for project-local launch context;
- explicit project-local pre-run workflow orchestration before the requested workflow executes;
- activation-time derivation of any selected execution working directory from launch-known inputs only;
- deterministic discovery of the project orchestration root;
- deterministic resolution of project-local workflow and profile references.

## What a playbook does not own

- connector semantics;
- workflow step semantics;
- runtime mode semantics such as `check`, `plan`, `execute`, or `explain`;
- hidden shell-first execution logic.

## Relationship to adjacent domains

- A workflow defines guarded operational intent.
- A profile defines reusable parameters, explicit overrides, and profile-scoped execution context.
- A playbook defines the project-local launch surface that selects one active profile per run and binds names to workflows, profiles, state declarations, logical state-role bindings, pre-run workflow orchestration, and other explicit execution context such as working-directory defaults and overrides.
- Runtime still owns mode behavior and execution semantics after playbook discovery and resolution complete.

## Quality bar

A good playbook:

- can be discovered predictably by both humans and agents;
- gives stable names to common project operations;
- keeps project-local launch concerns out of generic workflow logic;
- makes workflow, profile, and state resolution explicit enough for review;
- fails early when catalog entries are missing, ambiguous, or structurally invalid.

## Boundary rule

A playbook is not a workflow.

It is a project-level composition and launch document.
It may select, name, and parameterize workflows through explicit catalogs and defaults,
but it must not absorb the inner business-step logic that belongs in workflow files.
