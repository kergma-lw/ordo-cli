# Runtime UUID generation

## Contract

- `runtime.uuid.generate` is an action with no inputs and one `uuid: string` output.
- Each execution produces one canonical lowercase UUID version 4 using the platform's cryptographically secure random source.
- The generated value is execution-local until a later step passes it to another operation or persists it explicitly.
- Repeating the action produces a new value. The action offers probabilistic identifier uniqueness, not a reservation or atomic uniqueness guarantee in a remote system.
- The operation is not for credentials, authentication secrets, timestamps, or values that must survive another workflow run without explicit state storage.

## Runtime modes

- `check`, `review`, `plan`, `explain`, and `next` represent the step as an effectful future action and never generate a UUID.
- `run` generates the UUID only when the action step is reached, then makes it available through the registered step output.
- A workflow that needs stable reuse across runs must write the registered output to declared state and later read that state explicitly.

## Verification criteria

1. The published operation is an action with no inputs and `uuid: string` output.
2. Generated values parse as UUID version 4, use canonical lowercase text, and separate executions do not reuse a value.
3. A later step can consume the registered UUID output during one run.
4. Public help describes output scope, repeat behavior, remote-system uniqueness limits, and explicit state persistence.
