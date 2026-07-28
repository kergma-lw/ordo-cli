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

## Result model

Routine invocation returns the standard structured operation envelope, but with a bounded-output discipline.

Primary result fields should include:

- `status`;
- `summary`;
- optional `failure_mode`;
- `outputs` with compact machine-relevant fields such as verification verdict, selected observations, exit code, or log artifact path.

Full logs belong in runtime-owned temporary artifacts rather than inline as the primary payload.

## Probe output modes

Probe routines may be useful in at least two different ways:

- `mode: data` — the routine's main value is returned observation data and should prefer a structured format such as JSON;
- `mode: verify` — the routine's main value is a compact verification verdict plus bounded excerpts or highlights.

This distinction helps avoid treating all probe routines as if they returned the same kind of observation surface.

## Boundary rule

Routine identifiers are workflow-callable, but routine implementation logic is not workflow-owned structure.

The registry publishes a project-local invocation catalog.
It does not publish reusable connector semantics, and it must not silently widen back into arbitrary command execution.
