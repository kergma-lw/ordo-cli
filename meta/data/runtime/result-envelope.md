# Result envelope

## Minimal envelope

The runtime result must be able to express:

- overall status
- failed guard or failed step
- diagnostics
- outputs
- published workflow results
- skipped/executed steps
- human-readable message when useful for review
- machine-readable code when useful for classification

Connector operation results must also preserve enough structure for the runtime to expose:

- meaningful observations for successful probes
- meaningful effect summaries for successful actions
- structured failure diagnostics even when the underlying implementation raised an exception
- optional raw stdout/stderr detail fields when an implementation produces them

At minimum, a connector operation outcome should preserve:

- operation-local `status`
- short local `summary`
- structured `outputs` carrying observations or effect summary
- structured `diagnostics` when local problem detail matters
- optional supplementary `raw` detail

This operation outcome is the connector-local structured input to runtime adaptation, not the entire public runtime result envelope by itself.

## Workflow-local results and global publications

- Successful run output may include a workflow-local `results` list of authored return values produced by the requested workflow run.
- Each executed workflow `result` step appends one value to that workflow-local `results` list.
- Workflow-local result values accumulate in execution order inside that one workflow run.
- Successful run output may also include a global `published` list of authored published values.
- Each executed workflow `publish` step appends one value to that global `published` list.
- Published values accumulate in execution order across the enclosing run session, including nested `run` boundaries.
- Registering one `run` step should expose only the just-completed workflow-local `results` list rather than the global `published` stream.
- If `run` later supports bounded `for_each`, one registered caller value should preserve one array of per-run workflow-local result payloads rather than flattening all returned values into one list.
- The runtime must not inject additional metadata into authored `results` or `published` values in the initial model.
- If no `result` step executes, successful top-level run output may return `results: []` and may still choose one synthetic fallback result for compact human-facing run surfaces.
- Include expansion, playbook-owned `pre_run`, and nested reusable `run` boundaries must not emit fallback results of their own.

## Serialization constraints

- The public runtime result envelope is JSON-shaped.
- Contract-level result fields must be losslessly JSON-serializable.
- Python-specific, transport-specific, or format-specific value kinds must not be required by the public result contract.
- Human-readable summaries may be included, but machine-relevant meaning must remain available in structured fields.

## Baseline statuses

- `ok`
- `guard_failed`
- `validation_error`
- `resolution_error`
- `execution_error`
