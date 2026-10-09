# Generate execution-local UUID

You need one opaque identifier for later steps in the current workflow run.

Generate one lowercase UUID version 4 and return it for explicit use by later steps.

## Use when

- A later step needs a fresh opaque request, correlation, or idempotency identifier created during this run.

## What to provide

- No inputs. Register this action when a later step must read its `uuid` output.

## Result and boundary

- Returns `uuid` as one canonical lowercase UUID version 4 string. Each execution generates a new value.
- The result is execution-local until the workflow passes it onward or stores it. UUID generation makes collisions practically negligible, but it does not reserve or atomically prove uniqueness in a remote system.

## Do not use for

- A secret, credential, or authentication token; those need a contract that controls disclosure and retention.
- A value that must survive a later workflow run unless the workflow explicitly stores it in state.

## Related references

Use these related references when you need the generated value to outlive this run or to inspect another runtime operation.


- `ordo-help describe connector.runtime`: Parent connector family for current-run operations
- `ordo-help describe workflow.step.state_set`: Store a generated value explicitly when a later run must reuse it
- `ordo-help describe workflow.step.outputs`: Read the registered UUID output in a later step

## Examples

- Register runtime.uuid.generate, then pass step.request_id.outputs.uuid to the action that owns the remote resource.

## Inspect next

- workflow.step.outputs
- workflow.step.state_set
- connector.runtime

## Exact machine contract

Use `ordo-help operation runtime.uuid.generate --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### runtime_uuid_generate_for_later_step

Generate and register one UUID, then pass its explicit output to later workflow work. This checked example verifies the workflow shape, not random-number generation.

```yaml
version: 0
workflow: generate-request-id
blocks:
- steps:
  - name: generate-request-id
    uses: runtime.uuid.generate
    register: request_id
  - name: publish-request-id
    publish:
      request_id: step.request_id.outputs.uuid
```
