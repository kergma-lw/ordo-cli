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
  issue_ref: kergma-lw/ordo-cli#1

guards:
  - git.worktree.clean

steps:
  - name: inspect-issue
    uses: gh.issue
    with:
      issue_ref: ${inputs.issue_ref}
```

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
- only a minimal canonical operation set has concrete implementations;
- direct `${inputs.foo}` and `${states...}` step-value references exist but still represent an early runtime surface rather than a fully general expression system;
- some registry-visible operations still intentionally return structured not-yet-implemented results.

## 11. Runtime state example

`examples/open-task-from-gitx.yaml` now shows one small runtime state use:

- declare a named `states` location;
- write `states.task_state[inputs.issue_ref].branch` with `state_set`;
- read that value later through `${states.task_state[inputs.issue_ref].branch}`;
- remove it through `state_delete` when the workflow is done.

## Next docs

- `docs/ordo.1.md`
- `docs/contracts.md`
- `docs/format.md`
