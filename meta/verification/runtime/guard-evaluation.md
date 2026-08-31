# Guard evaluation runtime verification

## Rule

Guard evaluation results must remain explainable as a machine-usable runtime surface.

## Checks

- A blocked result identifies the blocking guard item.
- A blocked result identifies the failing subcondition when available.
- A blocked result identifies affected workflow inputs and workflow `let` bindings when available from guard dependency analysis.
- Runtime output distinguishes boolean guard failure from probe evaluation failure.
- Guard-evaluation traces remain structured enough for `check`, `plan`, and `explain` to report consistent blocker identity.
- Reuse of repeated identical probe references inside one expression does not weaken explainability.
