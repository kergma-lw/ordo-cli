# Ordo, pypyr, StackStorm, and Ansible

This document does not try to identify the best automation engine. It asks a narrower question: how can a recurring project process be described so that an AI agent can learn, before changing anything, whether the process is allowed and why?

## Ordo's model

Ordo workflows separate three concerns:

1. **Observations** are small, reusable facts about the current world: Git state, an issue, a Project field, saved context, or the result of an earlier step.
2. **Policy** combines observations through `let`, guards, and gates. It decides whether a workflow applies, whether a path is allowed, and why.
3. **Actions** have a clear effect: fetch a remote, create or switch a branch, change a Project field, or save context.

The aim is not an unlimited catalogue of checks. It is the ability to combine a small set of known observations and actions into a new project rule without writing a new monolithic helper.

For example, starting work may require all of the following:

```text
the issue is open
and its status is Ready
and the worktree is clean
and no different task is active
```

That is a new rule, but it can be expressed as policy before any branch is created or issue status is changed.

## What this comparison examines

All of the tools discussed here can express conditions, call commands, and be extended with code. The useful questions are instead:

1. Can observations become reusable, domain-level operations?
2. Can their results be combined into policy without turning every combination into new execution code?
3. Is policy separate from actions that change the world?
4. Can an agent receive one structured decision about whether the workflow is allowed and why?

## A composite admission decision

One Ordo workflow moves a Story to `Ready` only after it verifies all of the following:

- the Story is open, is a Story, is in `Backlog`, and the active profile is `meta`;
- every workspace profile is on `main` with a clean worktree;
- every issue linked from the Story's Markdown `Tasks` section is an existing `Task` or `Bug` in `Ready`;
- the Story contains no `TODO` or `TBD`, and has non-empty `Acceptance` and `Tasks` sections.

This is not one special-purpose probe. It combines Git, GitHub Project, Markdown, state, and profiles. It uses two `for_each` loops and places gates before the one changing action: changing the Story status. A failing linked task can identify the profile and issue that need attention.

Assume that each tool already has the domain operations needed to obtain these observations. The policy can still be expressed in all four systems, but it has a different shape:

- In **pypyr**, it needs `foreach` loops, assertions, and an explicit context accumulator if it must report every failure rather than stop at the first. The policy becomes pipeline control flow.
- In **StackStorm**, it needs a workflow of observation actions, loops, conditional transitions, and accumulated results. Rules alone do not fit, because there is no single incoming event with all the required data.
- In **Ansible**, it needs tasks with `loop`, `register`, and `failed_when` or `ignore_errors`, followed by aggregate `assert` or `fail` tasks. The policy is distributed across task results.
- In **Ordo**, the policy remains in guards, nested `for_each` blocks, and gates before the status-changing action.

The distinction is not whether the condition can be expressed. It is how an agent gets the answer, “May I run this?” In pypyr the answer is reconstructed from step order, loops, collected errors, and a final assertion. In Ansible it is distributed among tasks and registered results. In StackStorm it lives in workflow nodes and transitions; rules are useful when the condition is already in an event payload, but do not replace a composite local preflight. In Ordo, guards and gates make the admission basis explicit for `check` and `explain` before the changing action.

## Moving a workflow set to another project

The repository's `task-to-ready`, `set-active-task`, and `task-to-review` workflows form a concrete slice: move a task to `Ready`, prepare a work branch and move it to `In progress`, then render a diff and move the task to `In review`.

| Tool | What moves | What changes in the second project | Policy outcome |
| --- | --- | --- | --- |
| **Ordo** | Workflows, routine, diff script, registration, and profile | `repository` and `project_id`; explicit changes for status names, branch rules, or guards | Separate observations, guards/gates, and blocked results are retained; a new domain still needs new operations |
| **pypyr** | Pipelines, diff script, and any custom-step library | Confirm that the shared GitHub, Git, and state operations apply; define the pre-execution policy and its result | Context and conditions can compose policy, but the common admission result and explanation are a convention above the pipeline |
| **StackStorm** | A pack containing actions and workflows | Pack configuration, Git/GitHub observations, saved context, a manual API or CLI entry point, and an available platform | Rules and criteria are separate from actions but are oriented around trigger payloads; a local agent request needs another layer |
| **Ansible** | A role or playbook/task files and the diff script | Local inventory, variables, state, and GitHub Project access through `uri`/GraphQL or `gh` | Observations and conditions can be assembled from tasks, but one admission result and explanation must be derived from task-level results |

Existing libraries are not treated as an automatic advantage for any tool: a new domain observation must be implemented once everywhere. The comparison is about what happens after that operation exists—whether it can combine with other observations and actions without creating another monolithic ritual.

## When to choose a nearby tool

### pypyr

[pypyr](https://pypyr.io/) is a task runner for YAML pipelines with commands, shell, Python code, conditions, loops, retries, and error handling. It is a good fit for a flexible local automation pipeline. A custom-step library can provide domain observations and actions, but a workflow-wide admission decision, blocked reasons, and recovery guidance remain a convention designed above the pipeline.

### StackStorm

[StackStorm](https://stackstorm.com/) is an event-driven operations automation platform: sensors observe events, rules match criteria, actions do work, and workflows compose actions and retain execution state. It is a strong fit for webhooks, monitoring, messages, timers, and system integrations. Its rules answer, “Should this event trigger an action?” A local agent request about a repository needs a separate representation of local state and an explicit response shape.

### Ansible

[Ansible](https://www.ansible.com/) describes desired state for local or remote systems. Its playbooks combine tasks, facts, conditions, and error handling, while roles and variables support reuse in infrastructure automation. It can express a local ritual through `register`, `when`, `fail`, and custom messages, but these mechanisms primarily govern individual tasks and hosts; a workflow-wide admission decision and explanation must be assembled separately.

## Conclusion

Ordo does not claim to be functionally richer than pypyr, StackStorm, or Ansible. They are substantially more mature and richer in their primary domains.

Ordo's promise to a project owner is narrower:

> For known operational processes, an agent acts within explicit boundaries, and the owner can see why an action is allowed, blocked, or needs a preparatory step.

## Sources

### Ordo

- [Repository README](../README.md)
- [Workflow examples](../examples/)
- [Command-line reference](ordo.1.md)

### pypyr

- [pypyr home page](https://pypyr.io/)
- [Pipeline YAML structure](https://pypyr.io/docs/pipelines/pipeline-structure/)
- [Error handling](https://pypyr.io/docs/getting-started/error-handling/)

### StackStorm

- [Workflows](https://docs.stackstorm.com/workflows.html)
- [Rules](https://docs.stackstorm.com/rules.html)

### Ansible

- [Introduction to Ansible](https://docs.ansible.com/projects/ansible/latest/getting_started/introduction.html)
- [Conditionals](https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_conditionals.html)
- [Error handling in playbooks](https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_error_handling.html)
