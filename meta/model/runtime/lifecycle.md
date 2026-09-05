# Workflow lifecycle

## Minimal lifecycle

1. Parse
2. Validate
3. Resolve connector operations
4. Evaluate guards
5. Build plan / explain
6. Execute steps
7. Emit structured result

## Blocking states

- validation failed
- resolution failed
- guard failed
- execution failed

See `meta/model/runtime/check-semantics.md` for the normative rules that govern incomplete pre-execution verdicts and `pre_run`-related check behavior.

## Execution-tree mutation contract

The shared execution tree is the canonical runtime artifact once execute mode runs with tree assistance.

Required node-level runtime fields include at least:

- `runtime_status`;
- `revalidated`;
- `planned_observation`;
- `runtime_observation`;
- `divergence_status`;
- `divergence_reason`.

Execute mode may mutate only the execute-time fields that represent runtime progress, revalidation, reuse, and divergence.
Plan-time structural fields such as node identity, topology, and declared semantics remain stable.

When execute mode cannot use the shared tree safely, it must expose an explicit compatibility mode and fallback reason rather than silently pretending tree-driven execution happened.

## Deferred state nodes

Planning retains every top-level deferred `state_set`/`state_delete` node in
authored order. Its preflight status is `deferred`, its `reuse_policy` is
`not_reusable`, and its `planned_probe_result` is null. Preflight must not attach
mutation outputs or registers. Deferral does not reclassify the operation as
read-only or remove it from the execution plan.

When execution reaches an admitted mutation, it executes once in authored order,
with or without tree assistance. It must not reuse a simulated preflight result.
For deferred nodes, observation divergence is `not_applicable`, not a mismatch
against an invented planned mutation result. Ordinary runtime failures and
condition/gate semantics still apply; deferral is not a promise of success.

`plan`, `review`, `explain`, and `next` retain the check verdict's completeness
and unknown boundaries. An independent later false guard may block execution;
an invocation barrier after deferred state may leave relevant guards unevaluated.

## Planned fan-out node contract

If the product later adds bounded `for_each` on `run`, the shared tree should preserve that declared fan-out as one step-level structural node rather than flattening it into invisible repeated execution.

The tree-facing model should retain at least:

- that the node is one fan-out `run` step;
- whether the repeated body is a named `run` target or one inline short `steps` body;
- whether the whole step condition made the fan-out eligible, skipped, or still unknown;
- whether the source cardinality was statically known, statically zero, or runtime-only;
- the exact item count when statically known;
- the declared failure policy for repeated execution;
- whether caller-side `register` expects one aggregated array of per-run workflow-local result payloads.
- whether inner repeated-body step registers exist only as iteration-local runtime details rather than caller-visible aggregate outputs.

The runtime should preserve the difference between:

- fan-out blocked before expansion;
- fan-out skipped as a whole step;
- fan-out expanded with known count;
- fan-out retained as runtime-only cardinality.
