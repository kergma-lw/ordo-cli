# State Verification

## Contract Reference

The requirements in `meta/requirements/runtime/state.md` and model in
`meta/model/runtime/state.md` remain authoritative: state is cross-run memory,
not per-run scratch storage, and writes or deletes of an actual state storage
file belong after its final read, regardless of roles or profiles. Unbound
authoring retains the logical-role rule; bound validation uses actual storage
identity in each access context. This verification note does not narrow that contract.

## Authored-Order Coverage

`tests/test_state_role_write_order.py` verifies detection of later reads across
expression-bearing step and guard surfaces, referenced `let` bindings, mutation
key expressions, and nested inline steps. Unbound ordering is role-wide, not key-wide;
reads within the mutating step precede its mutation. Unused bindings and literal
text are not reads.

The tests cover early validation rejection in `check`, `review`, `plan`, `run`,
and `explain`, and the resulting ineligible `next` candidate. Invalid authored
order is rejected before observations, step execution, or state mutation.

## Bound Storage Coverage

`tests/test_state_storage_write_order.py` covers cross-role aliases, normalized
paths, symlinks, existing hardlinks, distinct files, read-first and same-step
access, missing bindings/declarations, and structured location failures.
`tests/test_state_storage_context.py` covers relative paths in static profile
contexts, same-role access to distinct files, input/let-resolved switches,
ignored switches, ambient control evaluation, and individual child validation.
The mode matrix covers `check`, `review`, `plan`, `run`, and `explain`; rejected
`next` candidates retain diagnostics and are ineligible without repeating checks.
Rejection precedes probes, state-content reads, operations, and mutations.

Proven violations use `validation.workflow.state_storage.write_before_last_read`.
Relevant unresolved write/later-read pairs use
`validation.workflow.state_storage.identity_unresolved`, explicitly not a proven
violation. Tests distinguish that conservative early rejection from read-only,
read-before-write, and known-disjoint access under uncertain contexts.

## Help Verification

The published `state`, `workflow.state_bindings`, `workflow.step.state_set`, and
`workflow.step.state_delete` examples include `state_bundle` verification.
The runner materializes existing world fixtures into temporary files, applies
explicit role bindings, and runs bound semantic validation. The positive bundle
reads through an alias before mutation, reuses the registered value afterward,
and includes a later independent input guard. The negative bundle verifies the
exact proven same-file diagnostic for a later read through another role/key.
These bundles cover fixed-file bound aliases without simulating execution.

Ordinary snippets still verify unbound authored validity; excerpts verify source
fidelity. Bundles do not verify check output, persistence effects, profile-relative
contexts, or symlink/hardlink fixtures. Those supported runtime behaviors remain
covered by runtime tests, not falsely attributed to the snippet runner. No such
unsupported fixture example is published as bundle-verified.

Readiness verification covers `ordo-help describe state`,
`ordo-help describe workflow.state_bindings`,
`ordo-help describe workflow.step.state_set`, and
`ordo-help describe workflow.step.state_delete`, using the checklist in
`meta/requirements/runtime/help-discovery.md`. Check the distinction between
durable state and registers, binding and mutation, staged diagnostics, and
larger intended-use fragments versus small syntax examples. Text, JSON, and
`ordo-help features` must communicate consistent ordering and top-level deferral
boundaries. Bundle syntax separates teaching-world bindings from authored text.
`tests/test_check_state_deferral.py` covers deferral execution behavior; the
validation-only bundle label does not establish it.

## Fragment Contract Drift

The normative restriction on mutation inside included or runtime-invoked
fragments applies. Include restrictions are published and enforced.
The bound `run` target tests allow state mutation in loaded child workflows with
individual child validation. This is a code/meta drift signal where
such children are runtime-invoked fragments, not approval to relax the fragment
contract. Reconciliation remains open; this verification note does not relax
fragment semantics or include restrictions.

## Cross-Invocation Verification Gap

Caller and child state-access streams are not flattened. Individual child
validation does not prove that a caller mutation precedes no child read, or that
a child mutation precedes no later caller/sibling read of the same storage.
These cross-invocation guarantees are not established by individual validation.
The top-level preflight invocation barrier after deferred state is conservative
analysis behavior, not a complete cross-invocation validator or execution ban.
Successful validation/check must not be described as full composed-run or
cross-run state-safety proof.

## Cross-Iteration Verification Gap

Cross-iteration state-order validation remains unresolved. The authored-order
validator visits an inline loop body once; it does not model a write at the end
of one iteration preceding a read in the next iteration. A body
that reads a role and then mutates it can therefore pass authored-order validation
even when repeated execution raises a cross-iteration ordering concern.

This is a known verification gap, not permission to use state as loop-local
scratch storage or a redefinition of the final-read contract. It does not establish
a general ban on writes in loops. Top-level preflight continuation is bounded by the
invocation barrier described in `check-semantics.md`; it does not analyze later
iterations or solve this gap.
Cross-iteration validation and the relationship between preflight observations
and state changed by earlier iterations require a separate semantic decision and
cross-mode verification before this gap can be considered resolved.
