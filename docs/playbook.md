# Ordo playbook draft

## Intent

The playbook is the project-local launch surface for Ordo.

It answers:

- which workflows are available in this project;
- which profiles are available for playbook runs;
- which project-local runtime state locations exist;
- how workflow logical state roles bind to concrete project state declarations.

It does **not** replace workflow semantics.
One playbook run activates one workflow.

## Canonical location

The canonical Ordo project file path is:

```text
.ordo/ordo.yaml
```

## Default discovery

When the caller does not provide an explicit playbook file path, the initial discovery rule is:

- look for `.ordo/ordo.yaml` relative to the current working directory.

The initial model deliberately does **not**:

- guess unrelated YAML files;
- silently fall back to alternate filenames such as `playbook.yml` or `playbook.yaml`;
- perform broad parent-directory crawling as hidden convenience behavior.

## Explicit file override

When the caller provides an explicit path through `--file PATH`, that path overrides default discovery.

## Initial shape

```yaml
version: 1

pre_run:
  - file: workflows/resolve-context.yml
    state_bindings:
      shared_context: repo_task_state

states:
  repo_task_state:
    path: .ordo/state/task-state.json

defaults:
  profile: backend-default

workflows:
  inspect-issue:
    file: inspect-issue.yml

  close-task:
    file: close-task.yml
    state_bindings:
      task_memory: repo_task_state

profiles:
  backend-default:
    file: backend-default.yml
```

## Stable top-level fields

- `version`
- `states`
- `defaults`
- `workflows`
- `profiles`
- `pre_run`

## Workflow entries

Each `workflows.<name>` entry gives a stable project-local name to one workflow file.

Initial stable fields:

- `file` — required workflow file reference;
- `state_bindings` — optional mapping from workflow logical state roles to concrete playbook state entries.

## Pre-run entries

Each `pre_run` item is a playbook-owned launch-phase entry.

Initial stable fields:

- `file` — required workflow file reference;
- `state_bindings` — optional mapping for state needed only by that pre-run launch phase.

Those bindings belong to the playbook launch wrapper rather than to the requested workflow contract.

## Profile entries

Each `profiles.<name>` entry gives a stable project-local name to one profile file.

Initial stable field:

- `file` — required profile file reference.

## State entries

Each `states.<name>` entry gives a stable project-local name to one runtime-managed state location.

Initial stable field:

- `path` — required storage path or location identifier.

## Defaults

Playbook defaults apply to one playbook run.

Initial stable default:

- `defaults.profile` — default active profile for the run when the caller does not select one explicitly.

## One workflow per run

The initial playbook model assumes one workflow per run.

Activation order is:

1. discover or load the playbook;
2. choose the active profile for the run;
3. select one workflow entry;
4. apply any explicit launch-time input overrides from the caller;
5. resolve requested-workflow state bindings;
6. execute any declared playbook-owned `pre_run` entries with their own launch-phase bindings;
7. enter the chosen runtime mode.

## Launch-time input overrides

`ordo-playbook` may list workflow entries first and then add or override top-level workflow inputs for one run with repeatable flags such as:

```text
ordo-playbook workflows list
ordo-playbook workflows show inspect-issue
```

Execution-oriented commands select the workflow positionally:

```text
ordo-playbook --input repository=repo/name --input issue_number=42 --input enabled=true plan inspect-issue
```

These launch-time input values are parsed as YAML scalars or collections and take precedence over both workflow-declared inputs and profile-provided default inputs for that run only.

For multiline string inputs, `ordo-playbook` may also read the value from a file:

```text
ordo-playbook --input-file body=./prompt.md plan inspect-issue
```

`--input-file` reads the file contents as a raw UTF-8 string for that one run. When both `--input` and `--input-file` set the same key, `--input-file` wins.

Workflow input declarations may also carry one optional `hint` string for invocation guidance. Discovery output such as `ordo-playbook workflows show <workflow>` should surface that hint alongside the input name and description.

`hint` is guidance only. It is not itself a validation rule.

## Successful run results

Successful `ordo-playbook run <workflow>` output is expected to surface the requested workflow's accumulated authored `results` list.

Those values come from executed workflow `result` steps in execution order for that one workflow run.

Executed workflow `publish` steps contribute separately to one global `published` list for the enclosing run session.

If no explicit `result` step publishes anything, the top-level successful run may emit one synthetic fallback result instead.

That fallback applies only to the requested top-level workflow run, not to internal include, `pre_run`, or nested `run` boundaries.

The runtime should not inject extra metadata into authored `results` or `published` values in the initial model.

## Resolution notes

- a bare workflow filename such as `close-task.yml` resolves under `.ordo/workflows/` relative to the playbook directory;
- a bare profile filename such as `backend-default.yml` resolves under `.ordo/profiles/` relative to the playbook directory;
- a relative state `path` resolves relative to the playbook directory;
- missing playbook discovery must fail explicitly rather than guessing another file.

## Current status

The playbook contract is now defined at the documentation/model layer.
The repository does not yet expose a stable end-user playbook CLI implementation.
