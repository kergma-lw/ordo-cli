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

The initial canonical playbook path is:

```text
.ordo/playbook.yml
```

## Default discovery

When the caller does not provide an explicit playbook file path, the initial discovery rule is:

- look for `.ordo/playbook.yml` relative to the current working directory.

The initial model deliberately does **not**:

- guess unrelated YAML files;
- silently fall back to alternate filenames;
- perform broad parent-directory crawling as hidden convenience behavior.

## Explicit file override

When the caller provides an explicit path through `--file PATH`, that path overrides default discovery.

## Initial shape

```yaml
version: 1

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

## Workflow entries

Each `workflows.<name>` entry gives a stable project-local name to one workflow file.

Initial stable fields:

- `file` — required workflow file reference;
- `state_bindings` — optional mapping from workflow logical state roles to concrete playbook state entries.

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
5. resolve state bindings;
6. enter the chosen runtime mode.

## Launch-time input overrides

`ordo-playbook` may add or override top-level workflow inputs for one run with repeatable flags such as:

```text
ordo-playbook --workflow inspect-issue --input repository=repo/name --input issue_number=42 --input enabled=true plan
```

These launch-time input values are parsed as YAML scalars or collections and take precedence over both workflow-declared inputs and profile-provided default inputs for that run only.

For multiline string inputs, `ordo-playbook` may also read the value from a file:

```text
ordo-playbook --workflow inspect-issue --input-file body=./prompt.md plan
```

`--input-file` reads the file contents as a raw UTF-8 string for that one run. When both `--input` and `--input-file` set the same key, `--input-file` wins.

## Resolution notes

- a bare workflow filename such as `close-task.yml` resolves under `.ordo/workflows/` relative to the playbook directory;
- a bare profile filename such as `backend-default.yml` resolves under `.ordo/profiles/` relative to the playbook directory;
- a relative state `path` resolves relative to the playbook directory;
- missing playbook discovery must fail explicitly rather than guessing another file.

## Current status

The playbook contract is now defined at the documentation/model layer.
The repository does not yet expose a stable end-user playbook CLI implementation.
