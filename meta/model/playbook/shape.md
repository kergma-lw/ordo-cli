# Playbook model shape

## Position

The playbook is the project-local orchestration root.

Canonical path in the initial model:

```text
.ordo/ordo.yaml
```

## Minimal shape

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
  working_directory: repos/default-backend

workflows:
  inspect-issue:
    file: inspect-issue.yml

  close-task:
    file: close-task.yml
    working_directory: ${inputs.repo_root}
    state_bindings:
      task_memory: repo_task_state

profiles:
  backend-default:
    file: backend-default.yml
```

## Stable top-level concepts

- `version` — playbook contract version;
- `states` — named project-local runtime state declarations;
- `workflows` — named launchable workflow entries;
- `profiles` — named launchable profile entries;
- `pre_run` — optional project-local launch-phase workflow set that executes before the requested workflow;
- `defaults` — optional playbook-run defaults such as the active profile.

## Pre-run role

`pre_run` is an optional ordered set of playbook-owned launch-phase entries.

Each entry declares the workflow `file` to execute in the same runtime session before the requested workflow begins its own effectful execution.

Each entry may also declare launch-phase-only bindings such as `state_bindings` that belong to the playbook wrapper rather than to the requested workflow contract.

The initial model treats `pre_run` as playbook-owned orchestration for shared preparation such as context resolution, environment checks, or runtime-profile switching.

That means the requested workflow does not need to declare logical state needs that are consumed only by `pre_run`.

## Workflow entry role

A workflow entry gives a stable project-local name to a workflow file.

It may additionally declare:

- state bindings from workflow logical roles to concrete playbook state entries;
- an explicit execution `working_directory` for runs of that workflow entry, expressed either as a literal path string or as an activation-time-safe `${...}` embedded-value local expression;
- future launch metadata that remains project-local rather than workflow-semantic.

## Defaults role

Playbook defaults apply to one playbook run.

The initial important defaults are:

- `defaults.profile` — the default active profile for the run when the caller does not select one explicitly.
- `defaults.working_directory` — the default execution working directory when neither the active profile nor the active workflow entry selects a more specific one.

## Profile entry role

A profile entry gives a stable project-local name to a profile file.

The profile file contributes runtime activation context for one playbook run.

That context may include:

- input bindings;
- approved overrides;
- a profile-scoped `working_directory` default, expressed either as a literal path string or as an activation-time-safe `${...}` embedded-value local expression;
- future runtime-facing execution selectors that remain declarative and reviewable.

Profiles do not create a second orchestration language.
They make project-local launch context explicit and reviewable.

## State entry role

A state entry gives a stable project-local name to a runtime-managed state location.

The initial standard field is:

- `path` — storage path or location identifier.

Future state metadata such as format, initialization policy, or backend kind may extend the state entry shape when runtime semantics standardize them.

## State binding role

A workflow entry may bind workflow logical state roles to concrete playbook state entries.

This keeps workflow authoring focused on logical state usage such as `task_memory`,
while the playbook owns the concrete project binding such as `repo_task_state`.

## Activation rule

The initial playbook model assumes one workflow per run.
The run selects one active profile, applies that profile, executes any declared `pre_run` workflows, and then activates one named workflow entry.
When execution working directory is declared at multiple playbook-owned launch surfaces, the more specific declaration wins in this order: playbook defaults, then active profile, then active workflow entry.
