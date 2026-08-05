# Included workflow fragment model

## Concept

An included workflow fragment is a reusable workflow-owned document that may be expanded into a caller workflow through one `include` item.

It is more than raw file splicing because the fragment may publish a local argument contract, but it remains part of workflow authoring rather than a separate connector-like abstraction.

This model describes the static-composition role of `include`.

If workflow reuse later needs caller-scoped runtime conditions, loops, or other invocation semantics, that pressure should be modeled as a separate invocation surface such as `run` rather than silently widening `include` beyond static composition.

## Authoring shape

An include call has two author-facing concerns:

1. resolve the fragment file through workflow include search rules;
2. optionally bind declared fragment arguments through `with`.

These are different internal concerns but they still belong to one static-composition primitive.

Illustrative include call:

```yaml
- include: github/check-issue
  with:
    repository: inputs.repository
    issue_number: inputs.issue_number
```

The `with` object belongs to the caller-side include site.

Its value expressions are authored in caller scope even though they are later bound into fragment-local `args...` references.

At the authored surface:

- plain scalar strings are caller-scoped expressions;
- quoted strings are explicit string literals;
- YAML numeric, boolean, and null scalars keep their ordinary literal meaning.

That binding model does not imply that `include` owns a general runtime invocation boundary.

## Fragment metadata

An included fragment may publish:

- `description` for human-oriented explanation;
- `args` for declared fragment-local inputs;
- ordinary workflow payload content such as `guards`, `steps`, or `blocks`.

The fragment-local `args` contract may use:

- a short form such as `repository: string` for one required argument;
- an object form when the fragment needs to declare `type`, `required`, or `default` explicitly.

Illustrative richer `args` shape:

```yaml
args:
  repository: string
  project_id:
    type: string
    default: null
  dry_run:
    type: boolean
    default: false
```

In this model:

- a short-form scalar declaration remains required unless a later contract revision says otherwise;
- `default` makes the argument optional for callers;
- `default: null` is valid and distinct from a missing required argument;
- an explicit caller binding of `null` remains semantically distinct from omission.

Illustrative fragment file:

```yaml
description: Check one issue and reuse the loaded result
args:
  repository: string
  issue_number: integer

blocks:
  - steps:
      - name: inspect
        uses: gh.issue
        with:
          repository: args.repository
          issue_number: args.issue_number
        register: issue
```

## Scope model

Within an included fragment instance:

- `args...` reads the fragment argument bindings for that instance;
- `inputs...` still reads the caller workflow inputs;
- `state...` still reads shared workflow state;
- `step...` reads registered step results from the same assembled workflow execution scope, including earlier caller-visible inline steps and earlier included-fragment steps.

An include-site `with` binding may therefore capture caller-local references, including caller `step...` results, as explicit argument inputs.

That capture does not replace the fragment's own direct access to the assembled workflow-local `step...` surface; it only adds fragment-local named argument bindings.

The `step...` surface therefore remains local to the assembled workflow execution scope rather than creating one isolated namespace per included fragment.

## Expansion semantics

Include expansion should be understood as:

1. resolve fragment location;
2. load fragment contract and payload;
3. validate `with` against declared `args`;
4. materialize omitted optional arguments from declared defaults, including `null` when declared;
5. bind fragment-local `args...` values from caller-scoped include bindings;
6. expand the fragment payload into the assembled workflow;
7. validate the assembled workflow.

This keeps the authoring surface simple while preserving explicit semantics for validation and diagnostics.
