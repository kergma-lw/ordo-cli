# Workflow value expressions

## Position

Value expressions provide a compact workflow-owned surface for deriving values from local runtime-visible inputs and prior registered step results.

They sit between two existing surfaces:

- plain scalar values with no runtime evaluation;
- connector operations and built-in runtime step forms that carry effects.

They are intended for local shaping of values, not for orchestration, policy, or integration logic.

## Core expression forms

The initial model supports three author-facing forms inside `${...}`:

- direct references such as `inputs.name`;
- direct references to prior registered step results such as `step.issue.outputs.id`;
- left-to-right filter pipelines using `|`;
- root built-in calls such as `format(...)`.

Illustrative examples:

```yaml
${inputs.repository}
${state.task_state[inputs.task_key].branch}
${step.issue.outputs.id}
${inputs.title | slug}
${inputs.title | trim | slug | truncate(60)}
${format("{}/{}-{}", inputs.type | lower, inputs.issue_number, inputs.title | slug)}
```

## Expression roots

The workflow-facing value-expression roots are:

- `inputs...` for declared workflow inputs;
- `state...` for persistent runtime state reads;
- `step...` for prior registered step results.

The `step...` root is execution-local and order-sensitive.

It is not a persistent storage surface.

## Filter pipeline

The pipe form `|` is the canonical compact composition surface.

It should be read left to right:

1. resolve the value on the left;
2. apply each built-in transform in order;
3. produce one final derived value.

The pipeline model is intentionally narrow:

- each stage is pure and deterministic;
- each stage consumes the previous stage output;
- the pipeline does not imply connector execution, control flow, or collection programming.

## Root built-ins

Some value operations are better expressed as a dedicated root built-in form than as an ordinary pipeline stage.

The first supported root built-in is `format(...)`.

Illustrative inline form:

```yaml
${format("{}/{}#{}", inputs.owner, inputs.repo, inputs.number)}
```

`format(...)` exists because workflows often need to compose multiple local values into one string while preserving a compact, reviewable surface.

## YAML equivalent forms

Some root built-ins may also define a structured YAML equivalent.

The structured equivalent is determined by the root expression form, not by arbitrary subexpressions inside the inline syntax.

The first dual-form built-in is `format`.

Illustrative YAML form:

```yaml
branch:
  format: "{}/{}-{}"
  args:
    - ${inputs.type | lower}
    - ${inputs.issue_number}
    - ${inputs.title | slug}
```

This YAML form exists for readability when the equivalent inline `format(...)` call becomes too dense.

Simple filter pipelines such as `${inputs.title | slug}` do not require a YAML equivalent.

## Initial built-in set

The initial built-in set should stay intentionally small.

Illustrative MVP set:

- `lower`
- `trim`
- `slug`
- `truncate(n)`
- `replace(from, to)`
- `format(...)`

This set is closed product surface, not workflow-defined or project-defined syntax.

## Examples

Branch name assembly:

```yaml
${format("{}/{}-{}", inputs.type | lower, inputs.issue_number, inputs.title | slug | truncate(60))}
```

Safe file name assembly:

```yaml
${format("{}_{}-{}-issue{}.md", inputs.ts, inputs.owner, inputs.repo, inputs.issue_number)}
```

Structured alternative for a longer formatted value:

```yaml
branch:
  format: "{}/{}-{}"
  args:
    - ${inputs.type | lower}
    - ${inputs.issue_number}
    - ${inputs.title | trim | slug | truncate(60)}
```

## Non-goals

Value expressions are not meant to become:

- a connector invocation surface;
- a second guard-expression language;
- an embedded conditional value-selection language;
- a general-purpose programming language;
- a workflow-defined macro system;
- an open-ended query or collection-transformation language.

They may evaluate predicates and return boolean values, but they must not choose between alternative values or subexpressions based on a runtime condition.

Illustrative forbidden forms include ternary syntax and helpers such as `if(...)`, `select(...)`, or `case(...)`.

They also must not read future step results or smuggle step-result access into guard evaluation.
