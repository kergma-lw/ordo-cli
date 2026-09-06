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

## Missing-Value Reporting Parity

The grouping contract in `meta/model/runtime/state.md` is narrow:
only emitted `runtime.value.state_missing` events with a private resolved target
are grouped in aggregate diagnostics. `src/ordo/model/diagnostic.py` implements
event counts, unique effective structural site paths in `reported_at` with
distinct expression/state references, first-seen ordering, singleton preservation,
and an empty aggregate path only for multiple sites.
No separate workflow field is published in a site. Private target identity uses
the resolved absolute location path, text key, and field path, not inode/symlink
equivalence or the bound write-order validator's broader alias identity.

The field is named `reported_at`, not `affected_sites`: these are the locations
of emitted diagnostic events, not a complete dependency or impact analysis.
`tests/test_state_missing_diagnostics.py` covers these distinctions and rejects
`affected_sites` as an alternative field name.

Reporting scope across the six public modes:

- `check` groups collected aggregate diagnostics without changing which expressions are evaluated.
- `review` retains the check diagnostics; grouping does not change review status or analysis.
- `plan` retains the check diagnostics without changing observations, cache reuse, or planned nodes.
- `run` groups aggregate diagnostics with structural attribution; operation-result diagnostics remain unchanged.
- `explain` carries the underlying result diagnostics without changing status or execution policy.
- `next` carries each candidate's check diagnostics locally; no cross-candidate grouping or eligibility/selection change is intended.

Grouping must not add evaluations or reads, change short-circuiting, or relax
existing barriers. This is a reporting contract, not a new evaluation/cache
policy. `tests/test_state_missing_diagnostics.py` exercises these reporting boundaries;
the next-candidate test checks candidate-local forwarding, not a full selection run.

The `state` feature entry and `ordo-help describe state` explain reporting scope;
grouping does not introduce another state operation, authoring form, or evaluation
rule. Help verification checks event counts, effective structural paths, private
diagnostic identity versus storage-alias identity, singleton behavior, and the
absence of source-line or separate workflow attribution. Read-before-write and
registered-reuse examples illustrate state use, not grouped runtime output.

The verified-snippet path validates authored workflows and bound ordering, not
runtime missing-value grouping. Runtime-output snippet coverage remains a gap.
The focused reporting test in `tests/test_ordo_help_cli.py` checks published
wording, not runtime behavior; neither its text/JSON assertions nor ordinary
authoring snippets prove grouping correctness.

## Named-Run Error-Path Coverage

Failed named-run binding materialization must be handled as a diagnostic, without
accessing workflow profile attributes on it. `tests/test_state_missing_diagnostics.py`
covers missing bindings in direct and nested calls, with and without fan-out,
while preserving normal profile propagation. Existing authoring snippets do not
exercise this error-return path.

## Dynamic-Key Input Usage

Input-usage analysis is distinct from state execution semantics. `check` records
`control_input` usage and mutation-site evidence for inputs in parsed `state_set`
and `state_delete` key expressions,
including nested state-key expressions. Quoted input-looking text in those keys
does not count as a reference; ordinary payload mapping keys remain data.
`review` must not report these inputs as declared but unused. `plan` and
`explain` retain the input-usage metadata; this classification does not change
`run` or `next` semantics. State-set value usage and classification precedence
are part of the coverage boundary.

`tests/test_state_target_input_usage.py` covers the four analysis modes, literal
and nested keys, value usage, evidence, and absence of state-file creation.
The dynamic `workflow.step.state_set` snippet uses its input only in the key
and writes a fixed value. The dynamic `workflow.step.state_delete` snippet also
demonstrates key-only usage.
`tests/test_help_snippets.py` separately checks both published snippets through
review; the snippet runner's label still means authoring validation, not proof
of classification or persistence.

Discovery verification checks the state feature, both mutation describe surfaces,
`workflow.inputs_contract`, and `workflow-rules.input_validation_default` for
consistent boundaries: input usage is neither an activation source nor proof of
validation. The analysis-tree model excludes meaningfully used inputs from
unused-declaration debt. Tests and snippet metadata must distinguish authoring
validation from runtime classification and persistence coverage; the presence
of a test is not evidence of a passing execution.

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
