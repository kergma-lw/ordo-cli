# Policy requirements

## Guard phase

- Guard evaluation must be a first-class runtime phase and not only an informal step convention.
- `check` must evaluate guards and static preconditions without executing effectful business steps.
- A blocked workflow result must identify the blocking guard or guards in machine-readable form.
- The runtime should be able to report more than the first blocking policy issue when such issues can be determined safely without execution.

## Positioning

- Ordo should remain meaningfully distinct from a generic pipeline/task runner by preserving its analysis-first and explain-first behavior.
- Ordo is not required to mimic existing pipeline tools when that would weaken guards, explainability, or structured results.
- Policy evaluation must remain an explicit runtime concern and must not be recoverable only by reading connector implementation code or shell control flow.
