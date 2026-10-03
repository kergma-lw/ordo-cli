# Ordo

[![Tests](https://github.com/kergma-lw/ordo-cli/actions/workflows/tests.yml/badge.svg)](https://github.com/kergma-lw/ordo-cli/actions/workflows/tests.yml)

> A runtime for local workflows that helps an agent check whether an action is allowed, explain that decision, and only then change project state.

Ordo is for a project owner who delegates work to an AI agent and does not want recurring development rituals to depend on the agent's guesses, long `AGENTS.md` instructions, or incidental error messages.

An Ordo workflow keeps three things distinct:

- **observations** about the current world, such as Git state, an issue, Project fields, or saved context;
- **policy**, which combines observations into the conditions for proceeding;
- **actions**, such as creating a branch, changing an issue status, or publishing changes.

A new ritual can combine existing observations and actions. Before running an action with side effects, an agent can ask whether the path is allowed and receive the reason when it is not.

## Good fit

- recurring repository rituals: starting a task, preparing work for review, publishing, or closing work;
- local automation with explicit admission rules and state checks;
- helpers for AI agents that need a structured answer instead of a guess from logs;
- workflows whose purpose and rules need to be reviewable and reusable.

## Not the goal

Ordo is not a replacement for a general orchestration platform, a CI service, or a general-purpose programming language in YAML. It is not intended to automate every process out of the box.

The project is still early-stage. Check the currently supported capabilities, limits, and examples before adopting it in a project.

## What it looks like

This small workflow reads a GitHub issue only when the worktree is clean:

```yaml
version: 0
workflow: inspect-issue
inputs:
  repository: kergma-lw/ordo-cli
  issue_number: 1
blocks:
- guards:
  - git.worktree.clean
- steps:
  - name: inspect-issue
    uses: gh.issue
    with:
      repository: inputs.repository
      issue_number: inputs.issue_number
    register: issue
```

The clean-worktree check is evaluated before the issue lookup. If it blocks the workflow, analysis modes report the reason instead of attempting the next step anyway.

## Examples

A supported installation path for using Ordo in another project will be documented separately. For now, explore the model through the examples in this repository.

[`examples/inspect-issue.yaml`](examples/inspect-issue.yaml) is a small entry point into the workflow format. More substantial project rituals live in [`.ordo/workflows`](.ordo/workflows).

## How Ordo differs from a task runner

A task runner primarily answers, “What should run?” Ordo also asks:

1. Does this workflow apply in the current state?
2. Which rules block it, if any?
3. Which steps would run, and which have side effects?
4. What is the next safe action?

Its central idea is the combination of declarative workflows, explicit admission rules, separate analysis modes, and structured results.

## Documentation

- [Workflow examples](examples/) — small working process descriptions.
- [Workflow format](docs/format.md) — the YAML model.
- [Command-line reference](docs/ordo.1.md) — available commands and their use.
- [Comparison with nearby tools](docs/comparison.md) — Ordo alongside pypyr, StackStorm, and Ansible.

## Security

Read [SECURITY.md](SECURITY.md) for workflow trust boundaries and vulnerability reporting.

## License

Ordo is free software licensed under the [GNU General Public License, version 3 or later](LICENSE).
