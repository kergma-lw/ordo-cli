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

guards:
  - should_run

steps:
  - name: print-branch
    uses: shell.command
    with:
      command: ${format("printf {}", branch)}
```

Use `let` when a guard, condition, or value expression would otherwise become too long or too repetitive inline.

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

Blocked example:

`examples/blocked-main-branch.yaml`

```bash
PYTHONPATH=src .venv/bin/python - <<'PY'
from pathlib import Path
from ordo import explain_workflow, load_workflow_file
from ordo.model.runtime import OperationResult

workflow = load_workflow_file(Path("examples/blocked-main-branch.yaml"))

def probe(resolved_guard, _workflow):
    if resolved_guard.reference == "git.branch":
        return OperationResult(status="ok", observations={"value": "main"})
    return OperationResult(status="ok")

result = explain_workflow(
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

`examples/set-active-task-from-gitx.yaml` now shows one small runtime state use:

- declare a logical `state_needs` role and bind it through the playbook layer;
- write `state.task_memory[inputs.task_key].branch` with `state_set`;
- read that value later through `${state.task_memory[inputs.task_key].branch}`;
- remove it through `state_delete` when the workflow is done.

## Next docs

- `docs/ordo.1.md`
- `docs/playbook.md`
- `docs/contracts.md`
- `docs/format.md`
