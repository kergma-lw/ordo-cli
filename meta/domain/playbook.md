# Playbook domain

## Role of the playbook

The playbook answers the question:

> which workflows are available in this project, under which names, with which project-local launch context.

It must not answer the question:

> what business steps a workflow performs internally.

Playbook files hold project-local launch intent and resolution context.
They may select, name, and parameterize workflows through explicit catalogs, defaults, and state bindings,
but they must not absorb workflow business-step logic.

## Playbook-owned routine surface

The playbook domain may also own a project-local routine catalog.

That catalog answers the question:

> which bounded project-local automation entries are intentionally published for workflow invocation in this project.

Routine entries are:

- project-local;
- named and reviewable;
- intentionally published rather than discovered from arbitrary repository scripts;
- opaque local automation boundaries rather than rich connector semantics.

Routines exist to provide a bounded invocation surface for project-local automation that would otherwise leak hidden shell-first behavior into workflow files.
They are not connector families and they do not create a second orchestration language.

## What a playbook owns

- project-local workflow catalog;
- project-local routine catalog;
- named profile catalog for playbook-run profile selection;
- named runtime state declarations shared across project workflows;
- bindings from workflow-level logical state roles to concrete project state declarations;
- project-local workflow-catalog navigation metadata such as category and operator-oriented usage timing;
- explicit execution working directory defaults and overrides for project-local launch context;
- shared connector-scoped ambient execution context for the project run surface;
- explicit project-local pre-run workflow orchestration before the requested workflow executes;
- explicit playbook-owned dependency bindings for that pre-run launch phase;
- activation-time derivation of any selected execution working directory from launch-known inputs only;
- deterministic discovery of the project orchestration root;
- deterministic resolution of project-local workflow and profile references.

## What a playbook does not own

- connector semantics;
- workflow step semantics;
- runtime mode semantics such as `check`, `plan`, `execute`, or `explain`;
- hidden shell-first execution logic.

The playbook domain may publish named routines for workflow use, but routine implementation detail must remain outside workflow files and must not silently widen into arbitrary command execution.

## Relationship to adjacent domains

- A workflow defines guarded operational intent.
- A profile defines reusable parameters, explicit overrides, and profile-scoped execution context.
- A playbook defines the project-local launch surface that selects one active profile per run and binds names to workflows, routines, profiles, state declarations, logical state-role bindings, pre-run workflow orchestration, and other explicit execution context such as working-directory defaults, connector context, and overrides.
- Runtime still owns mode behavior and execution semantics after playbook discovery and resolution complete.

## Quality bar

A good playbook:

- can be discovered predictably by both humans and agents;
- gives stable names to common project operations;
- gives stable names to intentionally published local automation when rich connector semantics are not yet available;
- keeps project-local launch concerns out of generic workflow logic;
- keeps pre-run launch dependencies in the playbook layer rather than leaking them into unrelated workflow state contracts;
- makes workflow, profile, and state resolution explicit enough for review;
- fails early when catalog entries are missing, ambiguous, or structurally invalid.

## Boundary rule

A playbook is not a workflow.

It is a project-level composition and launch document.
It may select, name, and parameterize workflows through explicit catalogs and defaults,
but it must not absorb the inner business-step logic that belongs in workflow files.

Project-local catalog metadata such as workflow `category` and operator-facing `when` guidance belongs to the playbook layer when it helps humans and agents choose the right workflow from the top-level launch surface.
That metadata must remain navigational and launch-oriented rather than becoming a second place to restate workflow step logic.
