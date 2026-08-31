# Guard evaluation runtime model

## Role

Guard evaluation is part of the runtime decision surface, not only a hidden implementation detail.
See also `meta/model/runtime/check-semantics.md` for the normative `check`-mode rules that constrain guard-coverage claims and incomplete preflight verdicts.
Step-derived read-only knowledge used by guard evaluation must follow the contract in `meta/model/runtime/preflight-step-interpreter.md`.

## Condition-surface summary

- `guards` answer whether workflow execution may cross an earlier workflow barrier.
- `if` answers whether one reached step should execute or be intentionally skipped.
- `gate` answers whether one reached step is admitted to execution and should fail when false.
- Across all three condition surfaces, failed read-only observation is evaluation failure rather than boolean `false`.

Compact summary:

| Surface | `false` means | evaluation failure means |
| --- | --- | --- |
| `guards` | workflow may not continue past the barrier | workflow applicability could not be established honestly |
| `gate` | the reached step is not admitted to execution | admission could not be established honestly |
| `if` | the reached step is intentionally skipped | step eligibility could not be established honestly |

## Minimum runtime structure

- A failed guard result must identify the blocking guard item.
- A failed guard result must identify the failing subcondition when available.
- A failed guard result must identify the affected workflow inputs and referenced workflow `let` bindings when that dependency path is statically knowable.
- Runtime outputs should preserve observed values when they materially explain the outcome.
- Runtime outputs should preserve a machine-usable evaluation trace rather than collapsing everything into a single boolean.

## Outcome distinctions

Runtime guard evaluation must preserve the distinction between:

- validation failure before guard evaluation;
- resolution failure before guard evaluation;
- boolean guard failure where evaluation completed and the condition was false;
- probe evaluation failure where the condition could not be safely evaluated.

## Trace expectations

- The trace should preserve boolean structure closely enough for explanation.
- Probe-level observations should remain attributable to the probe reference that produced them.
- A repeated identical probe reference within one expression should be reusable without requiring duplicate probe execution.
- Successful workflow-`let` expansion used by guard evaluation should remain visible enough for downstream diagnostics to attribute the blocking condition to the authored binding name.
