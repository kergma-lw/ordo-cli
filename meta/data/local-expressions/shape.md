# Local expression data shape

## Expression-bearing field families

The stable workflow contract may expose local expressions in more than one field family.

The important shape distinction is between native condition contexts, expression-first value contexts, and explicit embedded escape forms.

## Expression-first value form

An expression-first value context models a value-bearing field whose authored default is still an expression rather than a literal string.

Illustrative form:

```yaml
publish:
  title: step.issue.outputs.title
  summary: "Issue loaded"
```

Expression-first value rules:

- the surrounding field remains a value-bearing field rather than a dedicated condition list;
- plain authored scalar strings are local expressions by default;
- quoted authored strings are explicit string literals;
- if a plain authored scalar string is accepted as an expression, runtime evaluation failure must remain an expression error rather than silently degrading back into a literal string;
- YAML numeric, boolean, and null scalars retain their ordinary scalar meaning;
- nested object and list leaves follow the same rule recursively.

## Embedded expression form

An embedded expression appears inside a value-bearing field that still uses an explicit compatibility envelope for local expressions.

Illustrative form:

```yaml
with:
  repository: ${inputs.repository}
  branch: ${step.issue.outputs.branch}
```

Embedded-shape rules:

- the surrounding field remains a value-bearing field rather than a dedicated condition list;
- the expression form is explicitly embedded;
- the allowed roots still depend on the surrounding context.

## Native condition form

A native condition context may use direct expression items without an interpolation envelope.

Illustrative guard form:

```yaml
guards:
  - git.worktree.clean and git.branch.value != "main"
```

Native-condition rules:

- the surrounding field is already a condition-bearing surface;
- the condition item is authored directly as a local expression;
- context restrictions still determine which roots may appear.

## Current context-specific notes

- guard items are native condition entries;
- step `if` is a condition-bearing field whose preferred stable authored form is the native bare-expression surface;
- step `if: ${...}` remains supported as a deprecated compatibility form during migration;
- `with`, `value`, `publish`, `result`, and `for_each` are expression-first value-bearing surfaces;
- include-site `with` values are expression-first caller-scoped bindings;
- embedded `${...}` value forms remain available only as explicit escape forms for YAML-hostile expressions that are not viable as bare plain scalars.

This file describes only authored surface categories and stable reference forms.

It does not define the full semantic restrictions of each context.

## Root-shape notes

- `inputs...` is the stable workflow input reference form;
- `args...` is the stable included-fragment argument reference form;
- `state...` is the documented runtime-state read form where the surrounding context allows state reads;
- `step...` is the documented registered-step-result read form where the surrounding context allows execution-local step reads.

## Compatibility note

Current stable authored surfaces may include context-specific escape forms where YAML plain-scalar authoring is not viable.

Current compatibility decisions:

- object-form guard items using `uses` remain compatibility-only guard authoring surface;
- string-form native guard entries are the preferred stable guard form;
- step `if` prefers native bare condition entries;
- step `if: ${...}` remains a deprecated compatibility form;
- `${...}` inside expression-first value-bearing surfaces remains an explicit expression escape hatch rather than a general compatibility surface.

These escape forms do not change the higher-level local-expression model or the context restrictions that define which dependencies are allowed.
