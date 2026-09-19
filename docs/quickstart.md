# Quickstart

This quickstart shows the shortest useful path through the current Ordo v0 surface.

## 1. Use the project virtualenv

```bash
/home/ww/projects/ordo/.venv/bin/python -V
```

All examples below assume you run Python with `PYTHONPATH=src` from the repository root.

## 2. Inspect a workflow example

Start with a small workflow:

`examples/inspect-issue.yaml`

```yaml
version: 0
workflow: inspect-issue

inputs:
  repository: kergma-lw/ordo-cli
  issue_number: 1

guards:
  - git.worktree.clean

steps:
  - name: inspect-issue
    uses: gh.issue
    with:
      repository: ${inputs.repository}
      issue_number: ${inputs.issue_number}
```

If you want one example that already uses workflow-local named expressions, inspect:

`examples/let-bindings.yaml`

```yaml
version: 0
workflow: let-bindings
inputs:
  enabled: true
  type: Task
  issue_number: 7
let:
  should_run: inputs.enabled
  branch: format("{}/{}", inputs.type | lower, inputs.issue_number)
blocks:
- guards:
  - should_run
- steps:
  - name: publish-branch
    publish:
      branch: branch
```

Use `let` when a guard, condition, or value expression would otherwise become too long or too repetitive inline.
Here `publish` exposes the computed branch as data, not as shell command text; it does not create a Git branch.

## 3. Load and validate it

```bash
PYTHONPATH=src .venv/bin/python - <<'PY'
from pathlib import Path
from ordo import load_workflow_file, validate_workflow_document

workflow = load_workflow_file(Path("examples/inspect-issue.yaml"))
report = validate_workflow_document(workflow.to_contract())

print(report.status)
print([d.to_contract() for d in report.diagnostics])
PY
```

Expected result:

- status is `ok`
- diagnostics are empty

## 4. Discover what public operations exist

```bash
PYTHONPATH=src .venv/bin/python - <<'PY'
from ordo import get_public_connector_registry

registry = get_public_connector_registry()
for connector in registry.list_connectors():
    print(connector.namespace)
    for operation in connector.operations:
        print(" ", operation.name, operation.kind)
PY
```

At the moment the public families are:

- `git`
- `gh`
- `shell`

Real canonical implementations currently exist for:

- `git.worktree`
- `git.branch`
- `gh.issue`
- `shell.command`

Deprecated legacy compatibility probes still exist for object-form guards, including:

- `git.clean_worktree`
- `git.branch_not_main`
- `git.single_worktree`

## 5. Run `check`

```bash
PYTHONPATH=src .venv/bin/python - <<'PY'
from pathlib import Path
from ordo import check_workflow, load_workflow_file

workflow = load_workflow_file(Path("examples/inspect-issue.yaml"))
result = check_workflow(workflow)

print(result.to_contract())
PY
```

Use `check` when you want to know:

- does the workflow validate;
- do references resolve;
- do guards block execution right now.

`check` does **not** execute effectful business steps.

## 6. Run `plan`

```bash
PYTHONPATH=src .venv/bin/python - <<'PY'
from pathlib import Path
from ordo import load_workflow_file, plan_workflow

workflow = load_workflow_file(Path("examples/inspect-issue.yaml"))
result = plan_workflow(workflow)

print(result.to_contract())
PY
```

Use `plan` when you want to know:

- which guards are checked;
- which steps are expected;
- which steps are read-only vs effectful;
- whether execution is currently allowed.

## 7. Run `explain`

The Python API is `assess_workflow_readiness`, available from `ordo` and
`ordo.runtime`. The old Python name `explain_workflow` has been removed without a
compatibility alias. The CLI mode `explain` and result mode `Mode.EXPLAIN` are unchanged.

Blocked example:

`examples/blocked-main-branch.yaml`

```bash
PYTHONPATH=src .venv/bin/python - <<'PY'
from pathlib import Path
from ordo import assess_workflow_readiness, load_workflow_file
from ordo.model.runtime import OperationResult

workflow = load_workflow_file(Path("examples/blocked-main-branch.yaml"))

def probe(resolved_guard, _workflow):
    if resolved_guard.reference == "git.branch":
        return OperationResult(status="ok", observations={"value": "main"})
    return OperationResult(status="ok")

result = assess_workflow_readiness(
    workflow,
    guard_probe=probe,
)

print(result.to_contract())
PY
```

Use `explain` when you want structured reasoning for:

- why execution is blocked or allowed;
- what category of problem occurred;
- what the next safe action is.

## 8. Run `execute`

```bash
PYTHONPATH=src .venv/bin/python - <<'PY'
from pathlib import Path
from ordo import execute_workflow, load_workflow_file
from ordo.model.runtime import OperationResult

workflow = load_workflow_file(Path("examples/inspect-issue.yaml"))

result = execute_workflow(
    workflow,
    guard_probe=lambda _resolved, _workflow: OperationResult(
        status="ok",
        summary="clean",
        observations={"clean": True, "dirty_paths": []},
    ),
    step_executor=lambda _resolved, _workflow: OperationResult(
        status="ok",
        summary="inspected",
        observations={"issue": {"number": 1}},
    ),
)

print(result.to_contract())
PY
```

Important:

- `execute` respects guard semantics first;
- blocked-before-execution is distinct from execution failure;
- results stay structured on both success and failure paths.

## 9. Use a profile

Example profile:

`profiles/backend-default.yaml`

```bash
PYTHONPATH=src .venv/bin/python - <<'PY'
from pathlib import Path
from ordo import load_profile_file, load_workflow_file, plan_workflow

workflow = load_workflow_file(Path("examples/inspect-issue.yaml"))
profile = load_profile_file(Path("profiles/backend-default.yaml"))

result = plan_workflow(workflow, profile=profile)
print(result.outputs["active_profile"])
print(result.outputs["active_overrides"])
PY
```

Profiles are for:

- reusable defaults;
- reviewable presets;
- explicit overrides.

They are **not** a back door for silent semantic mutation.

## 10. Know the current limits

Right now Ordo is a Python API first.

Current important limits:

- no stable CLI yet;
- the initial playbook contract is documented, but the user-facing playbook CLI is still not implemented;
- only a minimal canonical operation set has concrete implementations;
- direct references, embedded-value pipelines, and dual-form `format` exist for local workflow value computation, but the surface remains intentionally small rather than a general programming language;
- some registry-visible operations still intentionally return structured not-yet-implemented results.

## 11. Runtime state example

[`examples/set-active-task-from-gitx.yaml`](../examples/set-active-task-from-gitx.yaml)
shows native project-policy gates and Git operations followed by task-state writes:

- supply `repository` and `project_id`; neither has an operational default;
- pass `allowed_issue_types` as a list, default `[Task, Bug]`, not a CSV string;
- bind the required logical `task_memory` role through the playbook layer;
- after branch selection, write issue number, input issue type/title, branch, and repository kind under `state.task_memory[inputs.task_key]`;
- optionally run `post_open_command` as explicit trusted code, skipped when empty.

This example does not read back or delete those state values. Project membership
and status changes precede Git operations and can remain after later failures;
branch creation and switching are separate and are not rolled back. Demo profile
project IDs are placeholders, not an operational setup. See the
[sequence and failure contract](gitx-open-task-rewrite.md); this example is not
equivalent to the canonical `.ordo` task workflow.

## Next docs

- `docs/ordo.1.md`
- `docs/playbook.md`
- `docs/contracts.md`
- `docs/format.md`
