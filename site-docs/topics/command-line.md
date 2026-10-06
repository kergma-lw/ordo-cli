# Command-line reference

Choose the public command that lets you inspect, validate, plan, or carry out workflow work.

Start by listing workflows, then use a non-changing mode before running a workflow that makes changes.

## Main entrypoint

Use `ordo-playbook` to work with the workflows published by the current playbook.

- `ordo-playbook workflows list` lists the workflows available in this project.
- `ordo-playbook workflows show <workflow>` shows what a named workflow needs before you run it.
- `ordo-playbook next` suggests the most useful workflow to consider next in the current context.
- `ordo-playbook graph` shows how published workflows share persistent data. Run it to see which workflows write, read, or remove that data; the result shows relationships, not a required run order. No active task is required.
- `ordo-playbook agent-instructions` reviews the whole playbook, then shows the compact Ordo-managed section for repository agent instructions when it is clean. Add `--write` only when you want it to update the repository AGENTS.md file.

## Choose a mode

- `ordo-playbook check <workflow>` answers whether the workflow can run now without changing anything.
- `ordo-playbook review` checks every declared workflow using authored playbook material only. It does not resolve caller inputs, read current state, or run probes. Missing input descriptions and missing input sources block dependent generation; style recommendations remain advisory. The report separately counts pipe-style recommendations so they remain visible.
- `ordo-playbook review <workflow>` reports workflow-quality issues for one workflow in its current context without changing anything.
- `ordo-playbook plan <workflow>` shows the work the workflow would perform without changing anything.
- `ordo-playbook run <workflow>` performs the workflow's real work and reports its result.
- `ordo-playbook explain <workflow>` explains why the workflow can or cannot run now.
- After adding or changing a workflow, run both `check` and `review`: readiness and workflow quality are separate questions.

## Repository instructions

- Run `ordo-playbook agent-instructions` to inspect the generated compact workflow guidance without changing files after a clean whole-playbook review.
- Run `ordo-playbook agent-instructions --write` to update only the managed section of the repository AGENTS.md file after that same clean review. Any finding reports the review and leaves the section unavailable and the file unchanged.
- The command does not choose workflows at runtime or replace repository guidance outside its marked section.

## Public flags

- `--file PATH` selects a playbook file for this command.
- `--profile NAME` selects a named profile for this command.
- `--input KEY=VALUE` supplies or replaces one input for this command; repeat it for more inputs.
- `--input-file KEY=PATH` supplies one input from a file; repeat it for more inputs.
- `--progress-steps` prints each step name as a run begins it.
- `--json` returns machine-readable output when another tool needs to consume the result.

## Input precedence

- For the same input key, the workflow's declared default is used first, then a selected profile fills the key only when it is still missing, then a concrete playbook workflow binding replaces it, and a command-line value replaces all of those for this run.
- If both `--input KEY=VALUE` and `--input-file KEY=PATH` name the same key, `--input-file` wins: Ordo reads the file's UTF-8 text as that input value.
- Within repeated uses of either one flag, the later value for the same key wins.

## Practical next steps

- Run `ordo-playbook workflows list` when you do not yet know the workflow name.
- Run `ordo-playbook review` to check the whole playbook, then `ordo-playbook check <workflow>` and `ordo-playbook review <workflow>` before relying on a changed workflow.
- Run `ordo-playbook plan <workflow>` to inspect intended work before `ordo-playbook run <workflow>` makes changes.
- Use `ordo-help command-line --json` when a tool needs the complete command contract.
- [`workflow-rules`](workflow-rules.md): Read the workflow authoring practices that make check and review complementary.
- [`overview`](overview.md): Find related public help surfaces.
