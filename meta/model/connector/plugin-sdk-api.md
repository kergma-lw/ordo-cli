# Concrete plugin SDK API proposal

## Role

This document turns the bounded plugin-SDK sketch into a concrete minimal authoring API proposal for the first implementation spike.

The goal is not to freeze every future detail.
The goal is to make the first code implementation possible without guesswork.

## Module-level shape

Each operation module should expose exactly two primary surfaces:

- `info()` — the uniform publication hook for the module;
- `run(ctx)` — the execution handler for the published operation.

The publication hook is the module's publication point.
The execution handler is the operation's execution point.

## Publication hook

The uniform publication hook should be:

```python
def info() -> PublishedOperation
```

`info()` should return a published operation definition that binds contract metadata and the execution handler explicitly.

Simple modules should not require any additional publication globals.

The first spike should not require operation-level ordering hints such as per-module `ORDER` values.
Operation publication should remain complete without a separate operation-order side channel.

## Published operation definition

The minimal published operation definition should expose at least:

- `name`
- `kind`
- `handler`
- `inputs`
- `outputs`
- `failure_modes`
- `effects`
- `prerequisites`

Implications:

- probe modules may leave `inputs`, `effects`, or `prerequisites` empty when not needed;
- action modules may leave `effects` empty only when the action has no narrower effect summary to declare;
- `prerequisites` here means operation-local prerequisites, not shared family bootstrap prerequisites.

The first spike may use separate published-definition types for probes and actions if that keeps the API simpler.

## Execution handler

The execution handler should be:

```python
def run(ctx: OperationContext) -> OperationOutcome
```

The first spike may use separate `ProbeContext` and `ActionContext` types only if the difference is concrete and small.
If the difference is weak, one `OperationContext` is preferred.

The handler should stay mode-agnostic.
It should not know whether runtime is currently building `check`, `plan`, `execute`, `explain`, or next-safe-action behavior.

## Operation context

The minimal context should expose at least:

- `input(name)` or equivalent access to operation-local inputs;
- `command(argv, *, failures=...)` for command-backed integration work;
- `bootstrap()` or equivalent access to shared family bootstrap/capability state;
- `call(name, *, inputs=None)` or equivalent explicit operation-to-operation dependency surface;
- narrow environment access when needed for local diagnostics or execution details.

The first spike should prefer plain, explicit names over abstraction-heavy helper layering.

## Approved operation dependency call

`ctx.call(name, *, inputs=None)` is a connector-author API, not a workflow expression or a new action-composition surface. A nonempty `inputs` mapping is supported only for same-family probe dependencies. Both fully qualified references such as `gh.pr.list` and family-local dotted names such as `pr.list` resolve within the caller's family. Cross-family dependencies are rejected.

Values in the mapping are already resolved by the caller. They are passed as values, without reevaluating workflow expressions or templates. Missing `inputs` and `inputs=None` retain the legacy no-input dependency behavior. A probe cannot invoke an action as a hidden mutation; this extension does not enable action-to-action composition.

For example, `gh.pr.create` delegates its mandatory complete open observation to `gh.pr.list` with resolved repository, head, source owner, base, and `state: open`. The connector consumes the probe outcome explicitly; a failed observation cannot become permission to mutate. `connector.authoring` provides reader-facing guidance for deciding when a new connector is warranted, but intentionally publishes no checked implementation example.

## Command helper

The concrete command helper should support this shape or a shape very close to it:

```python
ctx.command(
    ["git", "branch", "--show-current"],
    failures={
        "os_error": "git_unavailable",
        "nonzero": "probe_failed",
    },
)
```

The minimum normalized failure keys for the first spike should be:

- `os_error`
- `nonzero`

Additional keys such as timeout handling may be added later only if the first migrated operations need them.

## Command result

The command helper result should expose at least:

- `stdout`
- `stderr`
- `returncode`
- `raw`

If additional convenience accessors are introduced, they should remain small and obviously derived from those core fields.

## Operation outcome

The concrete local outcome type should expose exactly the structured surface already defined elsewhere in meta:

- `status`
- `summary`
- `outputs`
- `diagnostics`
- `raw`

The first spike should prefer one shared `OperationOutcome` shape unless probe/action differences require a second type in practice.

## Diagnostic type

The minimal local diagnostic type should expose at least:

- `code`
- `level`
- `message`
- `details`

Path-heavy runtime-specific structure should remain outside the local plugin SDK unless a first migrated operation proves it necessary.

## Convenience helpers

The first spike may provide small convenience helpers such as:

- `ok(...)`
- `fail(...)`
- `fail_with_diagnostic(...)`

Those helpers should only construct `OperationOutcome` values more concisely.
They should not replace or obscure the underlying structured outcome model.

`fail_with_diagnostic(...)` is appropriate when many operations would otherwise repeat the same pattern of:

- `status`
- `summary`
- one structured diagnostic code and message
- optional `details`
- optional `raw`

The helper should stay small and explicit rather than growing hidden policy or operation-kind-specific semantics.

## First-spike example shape

The intended first-spike authoring style is approximately:

```python
def info() -> PublishedOperation:
    return PublishedProbe(
        name="branch",
        outputs={"value": "string"},
        failure_modes=("git_unavailable", "not_repository", "probe_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    command = ctx.command(
        ["git", "branch", "--show-current"],
        failures={
            "os_error": "git_unavailable",
            "nonzero": "probe_failed",
        },
    )

    branch = command.stdout.strip()
    if not branch:
        return fail(
            code="probe_failed",
            summary="Current branch could not be determined",
            raw=command.raw,
        )

    return ok(
        summary="Current branch inspected successfully",
        outputs={"value": branch},
        raw=command.raw,
    )
```

This example is intentionally small.
If the first migrated files need substantially more ceremony than this, the SDK API should be reconsidered before wider rollout.

## Open questions intentionally left to the spike

The first implementation spike should answer these by code rather than by further abstract discussion:

- whether one `OperationContext` is enough or probe/action split pays for itself;
- whether one `PublishedOperation` type is enough or probe/action split pays for itself;
- operation dependency names and resolved-input probe calls are settled by the approved dependency contract above;
- whether `bootstrap()` should return one shared object or named capability views;
- whether convenience helpers are useful enough to keep after the first migrated operations.
