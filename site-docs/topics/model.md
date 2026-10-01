# Workflow model

Understand which domain owns each part of a workflow-enabled project.

Each section is a domain-owned explanation; use focused help for exact declarations.

## Open a focused guide


- `ordo-help describe workflow.workflow`: Name a workflow before defining its inputs, guards, steps, and outputs.
- `ordo-help describe playbook.workflows`: Publish a project's workflow catalog and activation context.
- `ordo-help describe profile.name`: Name a project's execution context.
- `ordo-help describe state`: Coordinate durable handoff between workflow stages.
- `ordo-help describe routine_contract`: Use a narrow local-automation fallback only when justified.

## Contracts



### Workflow contract

Use this contract to author a workflow file and keep its decisions explicit.



#### Start with

- Declare the workflow name and only the inputs it needs.
- Put applicability checks near the start.
- Use named steps and publish only the result a caller needs.

#### Related guidance


- [`workflow-rules`](workflow-rules.md): Choose the right conditional surface and validate changes with both check and review.
- [`capabilities`](capabilities.md): Confirm that the workflow surface you need is supported.

### Profile contract

Use profiles for deliberate project-local defaults such as inputs and working directory.



#### Use it for

- Select stable project context before a workflow runs.
- Keep workflow-specific decisions in the workflow rather than in a profile.
- Prefer published routines over deprecated launchers for small project-local helpers.

### Routine contract

Routines are a limited fallback, not the normal way to extend workflow authoring.



#### Before using a routine

- Check whether one published operation or a composition already fits.
- Use a routine only for a bounded local mechanical task. Do not hide an unclear product or workflow decision in its helper.
- Keep the helper's command, accepted values, success result, and named failure outcomes reviewable in the project.

#### Declare the routine

- Create `.ordo/routines.yaml` with `version: 1` and a `routines` map. Each named routine requires `kind`, `summary`, `implementation`, and `failure_modes`.
- Add `args` only for values callers must supply. Add `outputs` when the workflow needs structured success data, and use `log_hints` only for optional operational guidance.
- `implementation.argv` is required. It is a fixed command and argument list, not shell text. A whole item such as `{target}` is replaced by the declared `target` value; a list value expands to separate arguments.
- Name every expected failure outcome in `failure_modes`, such as `check_failed` or `runtime_unavailable`, so a failed helper remains understandable to its caller.

#### Call it deliberately

- A workflow step uses `routine.<name>`. Put required call values under `with.args`; do not pass unspecified caller data.
- Use `with.env` only for a short explicit list of scalar references such as `inputs.profile`. Ordo does not copy all workflow inputs into the helper environment automatically and generates the environment-variable names.

#### Complete author example

- Run `ordo-help describe routine_contract` to inspect the checked complete routine example. It declares `demo.echo`, its executable helper, the `{target}` placeholder, a named failure outcome, and a matching call. Start from that complete shape, then keep your helper equally small and local.
- `ordo-help describe workflow-rules.routine.*`: Read the fallback boundary before adding a routine.

#### Replacing a legacy launcher

- When replacing an existing launcher-based step, first identify the launcher record through profile.launchers and the operation step through workflow.step.launcher. Then decide whether the remaining local automation belongs in a small declared helper.
- `ordo-help describe profile.launchers`: Legacy launcher records to inspect during migration
- `ordo-help describe workflow.step.launcher`: Legacy operation-step launcher selection
- `ordo-help describe workflow-rules.routine.*`: Supported routine authoring path

### Playbook contract

Use a playbook as the project-local catalog and activation boundary for workflows.



#### Use it for

- List workflows that callers can discover.
- Provide project-owned defaults and state bindings.
- Describe when a workflow is appropriate in the project catalog.

#### Related guidance


- `ordo-help describe workflow.workflow`: Author the workflow body separately from its project catalog entry.
- [`command-line`](command-line.md): Run or inspect a published workflow through the public command line.

### State contract

Use state only for durable handoff between workflows, not ordinary workflow-local dataflow.



#### Keep state safe

- Bind state locations in the playbook.
- Keep stored values small and durable.
- Use step registers for data needed only during one workflow run.

#### Related guidance


- [`workflow-rules`](workflow-rules.md): Follow the lifecycle-state rule when deciding whether data belongs in state.
