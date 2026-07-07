# Included workflow fragment model

## Concept

An included workflow fragment is a reusable workflow-owned document that may be expanded into a caller workflow through one `include` item.

It is more than raw file splicing because the fragment may publish a local argument contract, but it remains part of workflow authoring rather than a separate connector-like abstraction.

## Authoring shape

An include call has two author-facing concerns:

1. resolve the fragment file through workflow include search rules;
2. optionally bind declared fragment arguments through `with`.

These are different internal concerns but together they still form one user-facing reuse primitive.

Illustrative include call:

```yaml
- include: github/check-issue
  with:
    repository: inputs.repository
    issue_number: inputs.issue_number
```

## Fragment metadata

An included fragment may publish:

- `description` for human-oriented explanation;
- `args` for declared fragment-local inputs;
- ordinary workflow payload content such as `guards`, `steps`, or `blocks`.

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
          repository: ${args.repository}
          issue_number: ${args.issue_number}
        register: issue
```

## Scope model

Within an included fragment instance:

- `args...` reads the fragment argument bindings for that instance;
- `inputs...` still reads the caller workflow inputs;
- `state...` still reads shared workflow state;
- `step...` reads only registered step results inside the same fragment-expanded execution scope.

The `step...` surface therefore remains local to its containing workflow or fragment execution scope rather than becoming a cross-fragment namespace.

## Expansion semantics

Include expansion should be understood as:

1. resolve fragment location;
2. load fragment contract and payload;
3. validate `with` against declared `args`;
4. bind fragment-local `args...` values;
5. expand the fragment payload into the assembled workflow;
6. validate the assembled workflow.

This keeps the authoring surface simple while preserving explicit semantics for validation and diagnostics.
