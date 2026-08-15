# Playbook routine model

## Position

The routine registry is a playbook-adjacent project-local catalog for bounded opaque automation.

It is not a workflow file and it is not a connector family.

Canonical default path in the initial model:

```text
.ordo/routines.yaml
```

## Minimal shape

```yaml
version: 1

routines:
  vikunja.backend.check:
    kind: action
    summary: Run Vikunja backend lint and web checks.
    args: {}
    implementation:
      argv: [".ordo/scripts/vikunja-helper", "backend", "check"]
    failure_modes:
      - tests_failed
      - helper_failed
      - runtime_unavailable

  vikunja.gh.issue-json:
    kind: probe
    summary: Return structured issue details from the upstream GitHub repository.
    args:
      repo:
        type: string
        required: true
      issue_number:
        type: integer
        required: true
    implementation:
      argv: [".ordo/scripts/vikunja-helper", "gh", "issue-json", "{repo}", "{issue_number}"]
    outputs:
      mode: data
      format: json
    failure_modes:
      - issue_not_found
      - helper_failed
      - runtime_unavailable
```

## Stable top-level concepts

- `version` — routine-registry contract version;
- `routines` — named project-local routine entries.

## Routine entry role

Each routine entry gives a stable project-local name to one intentionally published automation boundary.

Each routine entry declares at least:

- `kind` — `probe` or `action`;
- `summary` — short author-facing meaning;
- `args` — declared invocation arguments;
- `implementation` — the bounded implementation entry used by runtime;
- `failure_modes` — expected contract-level non-success classes.

Optional fields may additionally declare:

- `outputs` — expected probe output mode or format contract;
- `log_hints` — bounded diagnostic highlight hints;
- future local prerequisites or execution notes that remain reviewable and project-local.

## Implementation model

Routine implementation should prefer bounded argv materialization rather than unbounded shell grammar.

The initial implementation shape is:

```yaml
implementation:
  argv: [".ordo/scripts/example", "{arg}"]
```

This keeps the registry focused on published invocation contracts rather than becoming a second home for large embedded shell blocks.

## Invocation surfaces

Routine invocation has two distinct author-facing channels:

- `with.args` for declared business arguments that belong to the routine contract;
- `with.env` for explicit ambient execution context references that may influence local implementation behavior without widening the declared argument contract.

Illustrative call site:

```yaml
- uses: routine.python-lint
  with:
    args:
      target: inputs.target
    env:
      - inputs.review_mode
      - step.collect.outputs.value.path
```

In this model:

- `with.args` binds only names declared by the routine entry;
- `with.env` binds a short explicit list of supported workflow reference paths;
- `with.env` is a runtime execution-context surface, not part of the routine's declared business argument schema;
- workflow-visible environment bindings remain reviewable at the call site rather than hidden inside the routine implementation;
- runtime derives routine environment-variable names mechanically from the forwarded reference path, for example `inputs.profile` → `ORDO_INPUTS_PROFILE` and `step.collect.outputs.value.path` → `ORDO_STEP_COLLECT_OUTPUTS_VALUE_PATH`.

## Runtime-generated routine environment

Runtime may materialize only the references explicitly listed in `with.env` for a routine invocation.

- The model intentionally does not mirror every workflow `inputs.*` name into process environment variables.
- Broad automatic mirroring would hide routine dependencies, weaken reviewability, and make profile- or caller-provided surplus context look like a stable routine API.
- Runtime-generated environment names should remain mechanical and predictable rather than user-authored per-call shell API.
- Supported references should remain narrow and reviewable, beginning with roots such as `inputs.*` and `step.*` and expanding only when the runtime later standardizes additional roots.
- Forwarded references should resolve only to scalar values.
- If a forwarded reference resolves to an object or array, routine execution should fail rather than silently serializing structured data into an opaque shell-facing string.

This keeps routine environment access intentionally a little awkward, which is appropriate for an exception-path surface.

## Result model

Routine invocation returns the standard structured operation envelope, but with a bounded-output discipline.

Primary result fields should include:

- `status`;
- `summary`;
- optional `failure_mode`;
- `outputs` with compact machine-relevant fields such as verification verdict, selected observations, exit code, or log artifact path.

Full logs belong in runtime-owned temporary artifacts rather than inline as the primary payload.

When a routine primarily gathers data, that payload should stay honest and low-level.
Routine output should avoid silently embedding workflow-facing interpretation that would be clearer in published workflow surfaces.

## Probe output modes

Probe routines may be useful in at least two different ways:

- `mode: data` — the routine's main value is returned observation data and should prefer a structured format such as JSON;
- `mode: verify` — the routine's main value is a compact verification verdict plus bounded excerpts or highlights.

This distinction helps avoid treating all probe routines as if they returned the same kind of observation surface.

## Workflow-facing interpretation boundary

Routine implementation should prefer leaving shaping, projection, filtering, and lightweight interpretation to published workflow surfaces.

- Use routine logic for the narrow local mechanical gap itself.
- Keep workflow-facing data shaping visible in summary workflow surfaces such as representation adapters and local expressions.
- Avoid turning one probe routine into a hidden semantic adapter layer just because the local script already knows how to reshape the data.

## Boundary rule

Routine identifiers are workflow-callable, but routine implementation logic is not workflow-owned structure.

The registry publishes a project-local invocation catalog.
It does not publish reusable connector semantics, and it must not silently widen back into arbitrary command execution.
