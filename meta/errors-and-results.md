# Errors and results

## Structured result is required

Both a human and an agent must receive not only stdout/stderr,
but also a proper result object.

At minimum, the result must be able to express:
- success/fail/error;
- failed guard;
- executed/skipped steps;
- human-readable message;
- machine-readable code.

## Baseline categories

- `validation_error`
- `resolution_error`
- `guard_failed`
- `execution_error`

## Principle

If the runtime cannot explain a refusal in structured form,
the result contract is still immature.
