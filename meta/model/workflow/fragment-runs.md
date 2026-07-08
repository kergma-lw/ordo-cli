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
      if: ${step.issue.outputs.open}
      with:
        comment: "Issue is open."
        status: "In Progress"
```

This future shape should be read as:

1. declare one author-facing step that selects one reusable fragment reference;
2. optionally decide invocation eligibility in caller scope;
3. bind fragment `args` from caller-scoped values;
4. execute the fragment body within its own fragment-local execution scope.

## Boundary model

Within a future `run` call:

- caller-side `if` and `with` read caller workflow context;
- caller-side `with` may read prior registered caller `step...` results;
- fragment-local `args...` read the bound invocation arguments;
- fragment-body `step...` remains local to the invoked fragment execution scope rather than implicitly reading caller-local registers.

This preserves an explicit invocation boundary instead of treating caller-local runtime data as if it were authored directly inside the fragment body.

## Relationship to `include`

- `include` remains the static-composition primitive;
- `run` is the future runtime-scoped fragment invocation primitive;
- the same reusable fragment material may be suitable for one or both call sites depending on how it is authored and used;
- the distinction belongs primarily to call-site semantics rather than to a mandatory split in fragment file format.
