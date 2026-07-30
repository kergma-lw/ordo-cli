# Workflow fragment run model

## Status

This document describes a planned invocation-oriented reuse surface named `run`.

It is not part of the current stable workflow shape.

## Role

`run` exists for reusable workflow-fragment invocation when static `include` semantics are no longer sufficient.

Typical pressure for `run` includes:

- caller-scoped runtime conditions such as `if`;
- caller-scoped argument values that may depend on prior registered `step...` results;
- future invocation-scoped modifiers such as loops, if they are later introduced.

That same pressure also covers short repeated local bodies that are awkward to name as one-off fragments when the repeated logic is only a few steps long.

## Concept

A `run` step invokes one reusable workflow fragment as a runtime-scoped workflow node.

Unlike `include`, a `run` step does not merely disappear into static assembled structure before all runtime meaning is decided.

It owns an explicit caller/callee boundary.

## Minimal invocation shape

Illustrative future form:

```yaml
- steps:
    - name: comment-and-status
      run: github/comment-and-set-status
      if: step.issue.outputs.open
      with:
        comment: "Issue is open."
        status: "In Progress"
```

This future shape should be read as:

1. declare one author-facing step that selects one reusable fragment reference;
2. optionally decide invocation eligibility in caller scope;
3. bind fragment `args` from caller-scoped values;
4. execute the fragment body within its own fragment-local execution scope.

## Target resolution

`run` is the workflow-owned invocation surface for reusable fragment material.

If later workflow resolution allows more than one reusable target class behind `run`, local workflow fragments should resolve first on name collision.

That keeps the nearest workflow-owned fragment body as the default interpretation unless the product later introduces an explicit disambiguation surface.

## Boundary model

Within a future `run` call:

- caller-side `if` and `with` read caller workflow context;
- caller-side `with` may read prior registered caller `step...` results;
- fragment-local `args...` read the bound invocation arguments;
- fragment-body `step...` remains local to the invoked fragment execution scope rather than implicitly reading caller-local registers.

This preserves an explicit invocation boundary instead of treating caller-local runtime data as if it were authored directly inside the fragment body.

## Workflow-local results and caller registration

A `run` call may legitimately expose the callee workflow-local `results` list back to the caller through caller-side `register`.

- The registered caller-visible payload should reflect workflow-local return values of the just-completed callee run.
- It must not expose the enclosing run session's global `published` stream as if that were one callee-local return value.

## Planned bounded fan-out

If `run` later grows a bounded `for_each` modifier, that modifier belongs to the invocation surface rather than to a generic control-flow language.

- `for_each` should consume one array-valued source.
- The repeated body may be expressed either as one named `run` target or as one inline short `steps` body.
- Inline `steps` body exists for short local cycles; named `run` target exists for reusable or longer bodies.
- Caller-side `if` still applies to the whole declared step rather than to each item independently.
- Nested `for_each` anywhere inside the repeated body should stay invalid, including inside inline repeated-body `steps`.
- Nested `guards` inside the repeated body should stay invalid so applicability remains a workflow-level concern rather than an item-local control surface.
- If `register` is also present, the caller-visible payload should preserve one array of per-run workflow-local result payloads rather than flattening them.

## Iteration-local step scope for inline body

If a bounded fan-out later allows inline `steps`, those steps should execute in one iteration-local scope.

Within that scope:

- the current item binding is local to the iteration;
- any step `register` declared inside the inline body is visible to later steps in the same iteration body;
- that inner `register` does not leak automatically to sibling iterations or to caller scope;
- caller-visible aggregation still belongs only to the outer fan-out step `register`, whose payload is one array of per-run workflow-local result values.

## Relationship to `include`

- `include` remains the static-composition primitive;
- `run` is the future runtime-scoped fragment invocation primitive;
- the same reusable fragment material may be suitable for one or both call sites depending on how it is authored and used;
- the distinction belongs primarily to call-site semantics rather than to a mandatory split in fragment file format.
