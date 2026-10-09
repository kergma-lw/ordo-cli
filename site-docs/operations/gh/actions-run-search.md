# GitHub actions run search

Find every visible run of one workflow that carries a known correlation value in its run name.

Search one workflow's runs with exact GitHub event, ref, and run-name correlation.

## Use when

- A manually dispatched workflow sets its complete run name to the supplied request ID and the workflow needs to observe all matching runs.
- Zero and multiple matches remain explicit results; this probe does not select one run.

## What to provide

- `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide another OWNER/REPO to override that target.
- `workflow`: required; provide the GitHub workflow ID or file name.
- `event`: required; provide the GitHub event name.
- `ref`: required; provide the GitHub ref value without local normalization.
- `request_id`: required; provide the literal correlation value included in the workflow run name.

## Result and boundary

- The result includes `repository`, `workflow`, `event`, `ref`, `request_id`, `items`, `count`, and `complete`. `count=0` and `count>1` are successful results, not failures.
- `complete=true` means every accessible result page was read. Unavailable or incomplete listing has no usable result; a later GitHub change can alter the collection.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision.

## Do not use for

- Choosing one run from several matches, waiting for a run, or deciding whether a run passed.
- Finding a workflow whose complete run name is not request_id.

## Related references

Use these related references to submit a correlated request or inspect one chosen run.


- [`connector.gh.actions.dispatch`](actions-dispatch.md): Submit a manually dispatched workflow.
- [`connector.gh.actions.run`](actions-run.md): Observe one selected Actions run.

## Exact machine contract

Use `ordo-help operation gh.actions.run.search --json` when you need the exact machine-readable input and result contract for this operation.
