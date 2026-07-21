# Workflow domain

## Role of the workflow

The workflow answers the question:

> what to check, in what order, and which public operations to call.

It must not answer the question:

> how a transformation or integration algorithm is implemented internally.

Workflow files hold orchestration intent.
They may sequence checks, guards, steps, and explicit local composition surfaces,
but they are not the place where non-trivial transformation algorithms should be implemented.

## What is acceptable in a workflow

- ordered guard and step blocks;
- reusable included workflow fragments through assembly instructions;
- future invocation-oriented reusable fragment runs when static composition is insufficient;
- guard lists inside `guards` blocks;
- ordered steps inside `steps` blocks;
- compact references and parameters that remain workflow-semantic;
- logical state needs that express workflow-owned state roles without naming project storage instances;
- compact parameters;
- simple step-level conditional execution when it has clear semantics.
- simple branching when it has clear semantics.
- explicit authored result publication through existing `result` steps.
- optional author-provided invocation hints on input declarations.

Project-local launch context such as named workflow catalog, named profile catalog, and runtime state declarations belongs to the playbook contract rather than to the workflow domain itself.

## Assembly vs execution

An assembly instruction is a source-level workflow construct that shapes workflow assembly rather than surviving as a block kind in the assembled execution model.

`include` is the initial assembly instruction for static workflow composition.

The stable assembled execution shape is an ordered `blocks` list.
Each execution block declares exactly one of:

- `guards`
- `steps`

Top-level `guards` and `steps` may remain as compatibility-only authoring sugar when they normalize to the same block structure.

Assembly instructions may appear in source workflow material, but they do not survive as execution-semantic block kinds in the assembled workflow shape.

Assembly may still carry caller-scoped bindings into expanded material. That does not make the assembly instruction itself part of the assembled block model.

Named launch-time profile selection and project-local state declaration belong to playbook context rather than to generic workflow shape.

Included fragment reuse still belongs to the workflow domain when it remains declarative and workflow-semantic.

`include` specifically belongs to the static-composition side of that workflow reuse story.

If reusable fragments later need caller-scoped runtime modifiers or other invocation semantics, that pressure should be handled by a separate invocation surface such as `run` rather than by widening `include` until it stops being static composition.

That future distinction is acceptable inside the workflow domain because it separates two different jobs:

- `include` for static composition;
- `run` for runtime-scoped reusable-fragment invocation.

## Inclusion boundaries

Included fragments may declare local argument contracts.

Within an assembled workflow:

- `inputs...` remains global workflow input surface;
- `state...` remains global workflow state surface;
- `args...` is local to the included fragment instance that declared it;
- `step...` remains execution-local and must not cross included-fragment boundaries unless a later explicit export model is introduced.

## Public input contract

The public activation-input contract must stay readable from the root workflow.

- All user-facing activation inputs must be declared in the root workflow `inputs` contract.
- Any `inputs.<name>` reference that appears anywhere in the assembled workflow must refer only to a root-declared workflow input.
- Included fragments and reusable run targets may consume local `args...`, but they must not widen the public activation-input surface implicitly.
- Input-level `hint` text may help humans and agents choose values, but it remains guidance rather than a validation constraint.

## What is undesirable

- large embedded shell fragments;
- complex text transformations;
- project-specific knowledge baked into a generic workflow;
- hidden side effects.
- algorithmic transformation logic that belongs in connector operation code.

## Workflow quality

A good workflow:
- can be read quickly from top to bottom;
- can be explained in `plan` and `explain`;
- can be validated before execution;
- can show where one guard barrier ends and the next step sequence begins;
- can be moved across projects while preserving contracts.
- can be authored and iteratively repaired by a sufficiently capable agent using contract docs, examples, and structured diagnostics.

## Result publication

Workflow-owned result publication belongs to the workflow domain.

- Existing `result` step syntax remains unchanged.
- Each executed `result` step appends one authored value to the runtime results list.
- Published results accumulate in execution order rather than replacing prior published results.
- Published result values are stored as authored values only, without added runtime metadata.
