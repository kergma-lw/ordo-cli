# GitHub Actions dispatch and correlation requirements

## Dispatch action

- `gh.actions.dispatch` submits exactly one manual GitHub Actions workflow-dispatch request for one resolved repository, workflow file or numeric ID, ref, named inputs, and nonempty caller-provided `request_id`.
- A submitted dispatch confirms only that GitHub accepted the request. It does not establish a run identity unless GitHub returns one, completion, a tested checkout, or release approval.
- A refused request is distinct from an unknown submission result. Unknown submission must not be retried automatically because GitHub may already have accepted it.
- The action injects `request_id` as a workflow input. The caller must not duplicate it among ordinary named inputs.
- Dispatch is one effectful leaf action. It does not search, wait, poll, rerun, cancel, or interpret the resulting workflow.

## Run search probe

- `gh.actions.run.search` is a read-only probe over one repository workflow. It requires exact event, ref, and request ID inputs and returns every complete matching run collection.
- A workflow that is intended to be found through this probe must set its complete run name to the supplied request ID. Zero and multiple matches are successful observations and remain workflow-owned admission cases; the probe never chooses one.
- The correlation is an observation convention, not an atomic dispatch-to-run guarantee. A delayed run can appear after a zero-match observation.
- Search completion means all accessible result pages under the documented bound were read consistently. It does not attest workflow checkout, job success, or future collection stability.

## Release composition boundary

- A workflow may save a generated request ID and intended release facts before dispatch, then reconcile later through exact run search and one numbered run observation.
- The workflow, not either connector operation, owns cardinality gates, retry prohibition, terminal-state policy, tag verification, and any release authorization.
