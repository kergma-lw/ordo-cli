# State Verification

## Contract Reference

The requirements in `meta/requirements/runtime/state.md` and model in
`meta/model/runtime/state.md` remain authoritative: state is cross-run memory,
not per-run scratch storage, and writes or deletes of a logical state role belong
after its final read. This verification note does not narrow that contract.

## Authored-Order Coverage

`tests/test_state_role_write_order.py` verifies detection of later reads across
expression-bearing step and guard surfaces, referenced `let` bindings, mutation
key expressions, and nested inline steps. Ordering is role-wide, not key-wide;
reads within the mutating step precede its mutation. Unused bindings and literal
text are not reads.

The tests cover early validation rejection in `check`, `review`, `plan`, `run`,
and `explain`, and the resulting ineligible `next` candidate. Invalid authored
order is rejected before observations, step execution, or state mutation.

The published `workflow.step.state_set` and `workflow.step.state_delete` snippets
illustrate reading before mutation and using a registered value afterward. Their
snippet runner verifies authored validity, not executed state persistence.

## Cross-Iteration Verification Gap

Cross-iteration state-order validation remains unresolved. The
authored-order validator visits an inline loop body once; it does not model a
write at the end of one iteration preceding a read in the next iteration. A body
that reads a role and then mutates it can therefore pass authored-order validation
even when repeated execution raises a cross-iteration ordering concern.

This is a known verification gap, not permission to use state as loop-local
scratch storage or a redefinition of the final-read contract. This gap does not establish a
ban on writes in loops or change preflight or runtime traversal.
Cross-iteration validation and the relationship between preflight observations
and state changed by earlier iterations require a separate semantic decision and
cross-mode verification before this gap can be considered resolved.
