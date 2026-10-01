# Verified examples

Find a working repository example to inspect before authoring a similar workflow.

Each entry names a verified example file and the workflow behavior it demonstrates.

## How to use these examples

- Repository examples are complete files verified in this repository and linked from the generated site.
- A snippet-backed example is a smaller excerpt checked for a focused `ordo-help describe` guide. It can explain one surface but does not replace a complete repository example.

## Compatibility example

- The launcher-step example is retained for compatibility with older workflows. For new work, prefer routines or explicit profile context; run `ordo-help describe examples.launcher-step` for the migration-aware guide.

## Examples

- minimal: Minimal workflow example that composes one published operation into one small end-to-end workflow shape. See [examples/minimal.yaml](../examples/minimal.yaml).
- inspect-issue: Issue inspection example that uses a guard before loading one published GitHub issue probe. See [examples/inspect-issue.yaml](../examples/inspect-issue.yaml).
- inspect-pr: Pull-request inspection example that composes the published PR metadata, diff, comments, reviews, checks, and timeline surfaces into one summary. See [examples/inspect-pr.yaml](../examples/inspect-pr.yaml).
- set-active-task-from-gitx: Native task-activation sequence that checks project policy, updates status, fetches and fast-forwards the base, selects a task branch, and remembers task state, with an optional explicit trusted-code hook. See [examples/set-active-task-from-gitx.yaml](../examples/set-active-task-from-gitx.yaml).
- launcher-step: Launcher selection example that shows one step-level launcher override inside a profile-scoped execution context. See [examples/launcher-step.yaml](../examples/launcher-step.yaml).
- include-plain: Workflow include example that reuses one plain fragment without passing include arguments. See [examples/include-plain.yaml](../examples/include-plain.yaml).
- include-args: Workflow include example that passes explicit arguments into one reusable fragment contract. See [examples/include-args.yaml](../examples/include-args.yaml).
- playbook-workflows: Playbook workflow catalog example that shows one published workflow entry with defaults, profiles, and state bindings. See [examples/playbook-workflows.yaml](../examples/playbook-workflows.yaml).
- playbook-connectors: Playbook top-level example that shows the required version marker together with repository-wide connector defaults before workflow and profile activation. See [examples/playbook-connectors.yaml](../examples/playbook-connectors.yaml).
- playbook-pre-run: Playbook pre-run example that inserts one shared preparation workflow before the requested published workflow runs. See [examples/playbook-pre-run.yaml](../examples/playbook-pre-run.yaml).
- run-fan-out: Run-invocation example that contrasts named run-target fan-out with inline repeated steps, including outer if, gate, with, and register fields. See [examples/run-fan-out.yaml](../examples/run-fan-out.yaml).
- text-adapter: Text adapter example that projects, searches, and rewrites line-oriented text through the published text adapter surface. See [examples/text-adapter.yaml](../examples/text-adapter.yaml).
- local-expression-filters: Local-expression filter example that demonstrates type predicates, membership tests, and boolean flow over embedded values. See [examples/local-expression-filters.yaml](../examples/local-expression-filters.yaml).
- let-bindings: Workflow-local named expressions reuse input defaults in a boolean guard and publish a lowercased branch label as data, without running a shell command or creating a Git branch. See [examples/let-bindings.yaml](../examples/let-bindings.yaml).
- project-items-let: Project-items example that binds one collection probe through let and then filters it by field values. See [examples/project-items-let.yaml](../examples/project-items-let.yaml).
