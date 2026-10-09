# GitHub actions dispatch

Start one workflow that is configured for manual dispatch on a chosen branch or tag.

Submit one manual workflow start request with a ref and named input values.

## Use when

- The workflow already supports manual dispatch and the surrounding workflow has explicitly decided to start it.
- Provide the workflow file name or its positive numeric ID, the branch or tag ref to use, and at most 25 named input values.
- A submitted result confirms only that GitHub accepted the start request. It does not confirm that the workflow completed successfully.

## What to provide

- `workflow`: required; use a workflow file name ending in .yml or .yaml, or its positive numeric ID.
- `ref`: required; use a nonblank branch or tag name without control characters.
- `inputs`: required object; each key is a workflow input name and each value is a string, number, or boolean. Omit no required workflow inputs.
- `request_id`: required; provide the correlation value that the workflow puts in its run name. It is sent as the request_id workflow input.
- `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide another OWNER/REPO to override that target for this request.

## Result and boundary

- The result includes `repository`, `workflow`, `ref`, `request_id`, `submission`, `run_id`, `url`, `message`, and `errors`. `submission=submitted` confirms acceptance. When GitHub returns a run identity, `run_id` and `url` identify that run; they can otherwise be null.
- `dispatch_refused` confirms that GitHub rejected the request. `dispatch_unknown` confirms neither submission nor non-submission; inspect before deciding whether to submit again.
- This action does not wait, poll, rerun, cancel, or judge the dispatched workflow.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision. A successful change is not rolled back if a later workflow step fails.

## Do not use for

- Observing an existing Actions run or its jobs; use gh.actions.run and gh.actions.run.jobs.
- Automatically retrying an unknown submission result.

## Related references

Use these related references when the workflow needs to inspect Actions state before or after submission.


- [`connector.gh.actions.run.search`](actions-run-search.md): Find every run whose complete name equals this request ID when GitHub did not return a run identity.
- [`connector.gh.actions.run`](actions-run.md): Observe one known Actions run after its identity is available.
- [`connector.gh.actions.run.jobs`](actions-run-jobs.md): Observe all jobs for one identified Actions run attempt.
- [`connector.gh.repo.actions.permissions`](repo-actions-permissions.md): Inspect whether repository Actions are enabled before a hosted workflow change.

## Inspect next

- connector.gh.actions.run.search
- connector.gh.actions.run
- connector.gh.actions.run.jobs

## Exact machine contract

Use `ordo-help operation gh.actions.dispatch --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_actions_dispatch

Submit one manually dispatched deployment workflow for main with an explicit dry-run input. The published run identity identifies the accepted request, but does not establish completion or success.

```yaml
version: 0
workflow: dispatch-actions
inputs:
  repository: {}
  workflow: {}
  ref: {}
  request_id: {}
blocks:
  - steps:
      - name: dispatch-workflow
        uses: gh.actions.dispatch
        with:
          repository: inputs.repository
          workflow: inputs.workflow
          ref: inputs.ref
          request_id: inputs.request_id
          inputs:
            dry_run: true
        register: dispatched
      - name: require-submission
        gate: step.dispatched.outputs.submission | eq("submitted")
      - name: publish-dispatch
        publish:
          run_id: step.dispatched.outputs.run_id
          url: step.dispatched.outputs.url

```
