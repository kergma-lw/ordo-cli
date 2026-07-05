# Playbook scenarios

## Scenario 1: project-local workflow catalog

Repo exposes a small named set of common operational workflows through `.ordo/playbook.yml`.

Expected Ordo value:

- humans can discover available operations quickly;
- agents can target named workflows without reconstructing local bootstrap commands;
- project launch ergonomics improve without changing workflow semantics.

## Scenario 2: default profile selection

Playbook run selects a default profile such as `backend-default` before activating one workflow.

Expected Ordo value:

- common project defaults stay reviewable in one place;
- workflow files remain less repo-specific;
- callers may still override profile selection explicitly.

## Scenario 3: shared project state declaration

Multiple workflows use one named runtime state entry such as `task_state` declared in the playbook.

Expected Ordo value:

- state naming stays stable across workflows;
- storage location is managed in project-local orchestration context;
- workflows do not each duplicate the same storage declaration.

## Scenario 3b: launch-time input override

Caller launches a named workflow entry but needs to override one input such as `repository`, `issue_number`, or `enabled` for a single run.

Expected Ordo value:

- the caller can override or add the input without editing the workflow file;
- launch-time values win over workflow defaults and profile-provided defaults;
- the override remains local to that one run.

## Scenario 4: logical workflow state binding

Workflow uses a logical state role such as `task_memory`, while the playbook binds that role to a concrete state entry such as `repo_task_state`.

Expected Ordo value:

- workflow files stay portable across projects with different storage naming;
- playbook owns project-local storage binding rather than workflow files;
- missing bindings fail clearly before effectful execution.

## Scenario 5: missing playbook on default discovery

Caller runs `ordo plan close-task` in a directory without `.ordo/playbook.yml`.

Expected Ordo value:

- failure is immediate and explicit;
- runtime does not guess a workflow file from nearby YAML;
- both human and agent receive a clear next step.

## Scenario 6: unresolved named workflow

Playbook contains a named workflow entry whose target file no longer exists.

Expected Ordo value:

- validation or pre-execution resolution fails before effectful work;
- diagnostics name the missing entry and its target;
- the project can repair the catalog without inspecting runtime internals.

## Scenario 7: missing required state binding

Workflow declares `state_needs.task_memory`, but the active playbook workflow entry does not bind `task_memory`.

Expected Ordo value:

- activation fails before effectful execution;
- diagnostics identify the missing logical state role;
- runtime does not attempt to guess or auto-create a binding.
