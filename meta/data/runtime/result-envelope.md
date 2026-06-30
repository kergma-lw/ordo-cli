# Result envelope

## Minimal envelope

The runtime result must be able to express:

- overall status
- failed guard or failed step
- diagnostics
- outputs
- skipped/executed steps

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
