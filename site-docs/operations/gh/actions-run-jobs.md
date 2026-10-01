# GitHub actions run jobs

Supply required positive integer run_id and explicit positive integer attempt, normally from gh.actions.run outputs run_id and run_attempt. There is no latest-attempt default or caller limit; booleans are invalid identifiers.

Observe the complete job collection for one explicitly numbered GitHub Actions run attempt.

## Use when

- Repository is optional and nullable. Leave it out to use the workflow's GitHub repository context, or provide a valid ASCII OWNER/REPO value to inspect another repository. An invalid explicit value is rejected rather than falling back to the workflow target. The selected repository must be accessible to the authenticated GitHub command-line session.
- Outputs are repository, run_id, run_attempt, items, count and complete=true. Each item contains positive job_id, nullable check_run_id, and nullable name/status/conclusion/head_sha/url/started_at/completed_at. Present head_sha is a full hexadecimal SHA. Empty retrieval is items=[], count=0, complete=true, not successful CI.
- check_run_id is retained only when the job has a repository-matching check association, not from logs or display URLs. A missing link gives null identity; malformed or mismatched links fail. Correlate this ID with gh.pr.checks check-run item id, whose check_suite_id supplies the suite-to-run bridge.
- Traverse attempt-scoped pages of 100 jobs, up to 100 pages, requiring stable total_count, exact page sizes, valid page relations, unique job IDs and matching run/attempt per job. count equals len(items). Incomplete or inconsistent traversal fails rather than publishing partial success.
- Invalid repository, run ID, or attempt values are rejected. The result is unavailable when jobs cannot be read completely, do not belong to the selected run and attempt, have an invalid check association, or change while pages are read. Partial job lists are never returned as complete results.

## What to provide

- Provide required positive integer `run_id` and `attempt`, normally from `gh.actions.run` results. There is no latest-attempt default.
- Provide `repository` only to override the workflow GitHub repository context.
- `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call.
- `run_id`: required.
- `attempt`: required.

## Result and boundary

- Later steps can use `repository`, `run_id`, `run_attempt`, `items`, `count`, and `complete`. Each job item supplies `job_id`, status and conclusion facts, `head_sha`, and `check_run_id` when known.
- `complete=true` means the job collection was fully observed, including `items=[]` and `count=0`; it does not mean CI passed. Incomplete, contradictory, or unavailable pages fail instead of returning partial results. The collection is not an atomic snapshot.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision.

## Do not use for

- Selecting the latest attempt implicitly, triggering, rerunning, cancelling, polling, downloading logs, choosing required jobs, or enforcing merge policy; this is read-only observation.
- Treating complete as an atomic snapshot, CI success, or immutable event-time data. Cross-page and cross-probe observations are non-atomic.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.gh.actions.run`](actions-run.md): Resolve a run or suite association and pin its observed run_attempt before reading jobs
- [`connector.gh.pr.checks`](pr-checks.md): PR-attached status/check evidence, not an Actions job collection
- `ordo-help describe connector.gh`: GitHub access requirements and family operation boundaries

## Inspect next

- connector.gh.actions.run
- connector.gh.pr.checks
- connector.gh

## Exact machine contract

Use `ordo-help operation gh.actions.run.jobs --json` when you need the exact machine-readable input and result contract for this operation.

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
