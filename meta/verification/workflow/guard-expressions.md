# Guard expression verification

## Rule

Guard expressions must improve policy readability without collapsing explainability or machine-checkability.

## Checks

- Common execution conditions can be written more compactly than equivalent shell guard logic.
- Common execution conditions do not require creating a new bespoke public probe name for every simple predicate.
- Zero-argument probe references remain readable without mandatory empty call syntax.
- Boolean combinations inside one expression remain structured enough for validation and explanation.
- Runtime diagnostics can identify at least the failing subcondition, the observed value when available, and whether failure came from boolean mismatch or probe evaluation failure.
- Validation rejects statically invalid field paths against documented probe outputs.
- Guard resolution rejects effectful `action` operations inside expressions.
- Repeated identical probe references inside one expression need not be evaluated redundantly.
