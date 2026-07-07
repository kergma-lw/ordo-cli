# Workflow domain

## Role of the workflow

The workflow answers the question:

> what to check, in what order, and which public operations to call.

It must not answer the question:

> how a transformation or integration algorithm is implemented internally.

## What is acceptable in a workflow

- ordered guard and step blocks;
- reusable included workflow fragments;
- guard lists inside `guards` blocks;
- ordered steps inside `steps` blocks;
- compact references and parameters that remain workflow-semantic;
- logical state needs that express workflow-owned state roles without naming project storage instances;
- compact parameters;
- simple step-level conditional execution when it has clear semantics.
- simple branching when it has clear semantics.

The stable execution shape is an ordered `blocks` list.
Each block declares exactly one of:

- `guards`
- `steps`

Top-level `guards` and `steps` may remain as compatibility-only authoring sugar when they normalize to the same block structure.

Named launch-time profile selection and project-local state declaration belong to playbook context rather than to generic workflow shape.

Included fragment reuse still belongs to the workflow domain when it remains declarative and workflow-semantic.

The author-facing reuse surface may stay as one `include` primitive whether or not the included fragment binds arguments through `with`.

That user-facing unity is preferable to forcing authors to learn separate reuse verbs for non-parameterized and parameterized inclusion.

## Inclusion boundaries

Included fragments may declare local argument contracts.

Within an assembled workflow:

- `inputs...` remains global workflow input surface;
- `state...` remains global workflow state surface;
- `args...` is local to the included fragment instance that declared it;
- `step...` remains execution-local and must not cross included-fragment boundaries unless a later explicit export model is introduced.

## What is undesirable

- large embedded shell fragments;
- complex text transformations;
- project-specific knowledge baked into a generic workflow;
- hidden side effects.

## Workflow quality

A good workflow:
- can be read quickly from top to bottom;
- can be explained in `plan` and `explain`;
- can be validated before execution;
- can show where one guard barrier ends and the next step sequence begins;
- can be moved across projects while preserving contracts.
- can be authored and iteratively repaired by a sufficiently capable agent using contract docs, examples, and structured diagnostics.
