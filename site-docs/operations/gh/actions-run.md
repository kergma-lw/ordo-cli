# GitHub actions run

Supply exactly one non-null positive integer run_id or check_suite_id. Optional positive integer attempt selects that numbered attempt; omitted/null attempt reads the latest observed run_attempt, then retrieves the pinned numbered attempt. Booleans are not integer identifiers.

Observe one GitHub Actions run attempt, selected by a run ID or a check suite's direct Actions association.

## Use when

- Repository is optional and nullable. Leave it out to use the workflow's GitHub repository context, or provide a valid ASCII OWNER/REPO value to inspect another repository. An invalid explicit value is rejected rather than falling back to the workflow target. The selected repository must be accessible to the authenticated GitHub command-line session.
- For check_suite_id, resolve its directly associated Actions run and confirm the repository and suite identity. No repository-wide run scan is used. A known null association returns found=false, requested check_suite_id, repository, pull_requests=[], and all other run fields null. Missing association details fail, not normal absence.
- On found=true, outputs include repository, run_id, check_suite_id, run_attempt, workflow_id, workflow_path, event, status, conclusion, head_sha, head_branch, url, created_at, updated_at, run_started_at, and pull_requests with number/head_sha/base_sha. Optional GitHub facts remain null; missing pull_requests becomes []. Present SHAs are full hexadecimal values. Output run_attempt becomes the explicit attempt input to gh.actions.run.jobs.
- Invalid selectors, attempts, or repository values are rejected. If the selected run cannot be read, is inconsistent with the selected repository or suite, or returns incomplete data, the result is unavailable. A missing run is not found=false; found=false only describes a check suite with no associated Actions run.

## What to provide

- Provide exactly one required positive integer: `run_id` or `check_suite_id`. Do not provide both. `attempt` is optional; when omitted or null, the operation observes the latest attempt and then pins that numbered attempt.
- Provide `repository` only to override the workflow GitHub repository context. Use `check_suite_id` from a pull request check when the workflow needs its directly associated Actions run.
- `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call.
- `run_id`: conditional.
- `check_suite_id`: conditional.
- `attempt`: optional.

## Result and boundary

- When `found=true`, later steps can use `run_id`, `check_suite_id`, `run_attempt`, `head_sha`, lifecycle facts, and `pull_requests`. Pass `run_id` and the returned `run_attempt` to `gh.actions.run.jobs`.
- For a known check suite without an associated run, `found=false` is the result; it is not a failed run. Unknown or unavailable observations fail rather than reporting absence. The latest-then-pinned lookup is non-atomic and does not establish merge policy.
- Usable result fact: `repository`.
- Usable result fact: `workflow_id`.
- Usable result fact: `workflow_path`.
- Usable result fact: `event`.
- Usable result fact: `status`.
- Usable result fact: `conclusion`.
- Usable result fact: `head_branch`.
- Usable result fact: `url`.
- Usable result fact: `created_at`.
- Usable result fact: `updated_at`.
- Usable result fact: `run_started_at`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision.

## Do not use for

- Run triggering, reruns, cancellation, polling, log retrieval, required-job selection, or merge policy. This is read-only observation.
- An immutable event snapshot: PR head/base SHAs are GitHub observations. Latest-then-pinned retrieval is non-atomic and does not promise the newest attempt at return time.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.gh.actions.run.jobs`](actions-run-jobs.md): Full jobs traversal using the observed run_id and explicit attempt=run_attempt
- [`connector.gh.pr.checks`](pr-checks.md): PR-attached check runs expose nullable check_suite_id as the selector bridge
- [`connector.gh.repo.actions.permissions`](repo-actions-permissions.md): Repository Actions permission settings, not run observations
- `ordo-help describe connector.gh`: GitHub access requirements and family operation boundaries

## Inspect next

- connector.gh.actions.run.jobs
- connector.gh.pr.checks
- connector.gh

## Exact machine contract

Use `ordo-help operation gh.actions.run --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_actions_direct

Observe a known run, then pass its registered run_id and latest observed run_attempt to pinned jobs. Require complete collection before publishing every job; count=0 is valid. The workflow keeps run and attempt identities explicit, requires a complete job collection, and does not establish an atomic snapshot or merge policy.

```yaml
version: 0
workflow: inspect-actions
inputs:
  repository: {}
  run_id: {}
blocks:
  - steps:
      - name: observe-run
        uses: gh.actions.run
        with:
          repository: inputs.repository
          run_id: inputs.run_id
        register: observed
      - name: require-found-run
        gate: step.observed.outputs.found | eq(true)
      - name: observe-pinned-jobs
        uses: gh.actions.run.jobs
        with:
          repository: inputs.repository
          run_id: step.observed.outputs.run_id
          attempt: step.observed.outputs.run_attempt
        register: jobs
      - name: require-complete-jobs
        gate: step.jobs.outputs.complete | eq(true)
      - name: publish-observation
        publish:
          run_id: step.observed.outputs.run_id
          run_attempt: step.observed.outputs.run_attempt
          items: step.jobs.outputs.items
          count: step.jobs.outputs.count
          complete: step.jobs.outputs.complete

```
### gh_actions_bridge

Read complete PR checks, select check runs by explicit check_suite_id (several checks may share a suite), resolve the suite through gh.actions.run, gate on found, and pass registered run_id/run_attempt to complete jobs. No run ID is guessed from a check ID or URL. The workflow keeps run and attempt identities explicit, requires a complete job collection, and does not establish an atomic snapshot or merge policy.

```yaml
version: 0
workflow: inspect-actions
inputs:
  repository: {}
  pull_number: {}
  check_suite_id: {}
blocks:
  - steps:
      - name: inspect-checks
        uses: gh.pr.checks
        with:
          repository: inputs.repository
          pull_number: inputs.pull_number
          target: 'head'
        register: checks
      - name: require-complete-checks
        gate: step.checks.outputs.complete | eq(true)
      - name: require-suite-selector
        gate: inputs.check_suite_id | is_integer
      - name: select-suite-checks
        value: step.checks.outputs.checks | only(kind="check_run") | only(check_suite_id=inputs.check_suite_id)
        register: selected
      - name: require-selected-suite
        gate: step.selected.outputs.value | length | ne(0)
      - name: observe-run
        uses: gh.actions.run
        with:
          repository: inputs.repository
          check_suite_id: inputs.check_suite_id
        register: observed
      - name: require-found-run
        gate: step.observed.outputs.found | eq(true)
      - name: observe-pinned-jobs
        uses: gh.actions.run.jobs
        with:
          repository: inputs.repository
          run_id: step.observed.outputs.run_id
          attempt: step.observed.outputs.run_attempt
        register: jobs
      - name: require-complete-jobs
        gate: step.jobs.outputs.complete | eq(true)
      - name: publish-observation
        publish:
          run_id: step.observed.outputs.run_id
          run_attempt: step.observed.outputs.run_attempt
          items: step.jobs.outputs.items
          count: step.jobs.outputs.count
          complete: step.jobs.outputs.complete

```
### gh_actions_null_suite

The same bridge gates before run lookup when the suite selector is null. Nullable check_suite_id is normal; it cannot identify an Actions run. The workflow keeps run and attempt identities explicit, requires a complete job collection, and does not establish an atomic snapshot or merge policy.

```yaml
version: 0
workflow: inspect-actions
inputs:
  repository: {}
  pull_number: {}
  check_suite_id: {}
blocks:
  - steps:
      - name: inspect-checks
        uses: gh.pr.checks
        with:
          repository: inputs.repository
          pull_number: inputs.pull_number
          target: 'head'
        register: checks
      - name: require-complete-checks
        gate: step.checks.outputs.complete | eq(true)
      - name: require-suite-selector
        gate: inputs.check_suite_id | is_integer
      - name: select-suite-checks
        value: step.checks.outputs.checks | only(kind="check_run") | only(check_suite_id=inputs.check_suite_id)
        register: selected
      - name: require-selected-suite
        gate: step.selected.outputs.value | length | ne(0)
      - name: observe-run
        uses: gh.actions.run
        with:
          repository: inputs.repository
          check_suite_id: inputs.check_suite_id
        register: observed
      - name: require-found-run
        gate: step.observed.outputs.found | eq(true)
      - name: observe-pinned-jobs
        uses: gh.actions.run.jobs
        with:
          repository: inputs.repository
          run_id: step.observed.outputs.run_id
          attempt: step.observed.outputs.run_attempt
        register: jobs
      - name: require-complete-jobs
        gate: step.jobs.outputs.complete | eq(true)
      - name: publish-observation
        publish:
          run_id: step.observed.outputs.run_id
          run_attempt: step.observed.outputs.run_attempt
          items: step.jobs.outputs.items
          count: step.jobs.outputs.count
          complete: step.jobs.outputs.complete

```
### gh_actions_no_run

The same bridge stops at the found gate when the suite has no associated Actions run (found=false). Jobs never receives a guessed run or null attempt. The workflow keeps run and attempt identities explicit, requires a complete job collection, and does not establish an atomic snapshot or merge policy.

```yaml
version: 0
workflow: inspect-actions
inputs:
  repository: {}
  pull_number: {}
  check_suite_id: {}
blocks:
  - steps:
      - name: inspect-checks
        uses: gh.pr.checks
        with:
          repository: inputs.repository
          pull_number: inputs.pull_number
          target: 'head'
        register: checks
      - name: require-complete-checks
        gate: step.checks.outputs.complete | eq(true)
      - name: require-suite-selector
        gate: inputs.check_suite_id | is_integer
      - name: select-suite-checks
        value: step.checks.outputs.checks | only(kind="check_run") | only(check_suite_id=inputs.check_suite_id)
        register: selected
      - name: require-selected-suite
        gate: step.selected.outputs.value | length | ne(0)
      - name: observe-run
        uses: gh.actions.run
        with:
          repository: inputs.repository
          check_suite_id: inputs.check_suite_id
        register: observed
      - name: require-found-run
        gate: step.observed.outputs.found | eq(true)
      - name: observe-pinned-jobs
        uses: gh.actions.run.jobs
        with:
          repository: inputs.repository
          run_id: step.observed.outputs.run_id
          attempt: step.observed.outputs.run_attempt
        register: jobs
      - name: require-complete-jobs
        gate: step.jobs.outputs.complete | eq(true)
      - name: publish-observation
        publish:
          run_id: step.observed.outputs.run_id
          run_attempt: step.observed.outputs.run_attempt
          items: step.jobs.outputs.items
          count: step.jobs.outputs.count
          complete: step.jobs.outputs.complete

```
