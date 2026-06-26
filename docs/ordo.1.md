# ORDO(1)

## NAME

**ordo** - contract-first local workflow runtime for guarded operational automation

## SYNOPSIS

Ordo currently exposes a Python API rather than a stable CLI.

```python
from pathlib import Path

from ordo import (
    check_workflow,
    execute_workflow,
    explain_workflow,
    load_profile_file,
    load_workflow_file,
    plan_workflow,
)

workflow = load_workflow_file(Path("examples/inspect-issue.yaml"))
profile = load_profile_file(Path("profiles/backend-default.yaml"))

check_result = check_workflow(workflow, profile=profile)
plan_result = plan_workflow(workflow, profile=profile)
execute_result = execute_workflow(workflow, profile=profile)
explain_result = explain_workflow(workflow, profile=profile)
```

## DESCRIPTION

Ordo is a small analysis-first runtime for local workflows.

It is built around:

- declarative workflows;
- explicit guards;
- explicit steps;
- public connector operations;
- structured runtime results.

The core promise is that a workflow can be checked, planned, explained, and only then executed.

## CURRENT STATUS

The repository now contains a real v0 foundation.

It already supports:

- workflow and profile loading from YAML;
- strict validation with structured diagnostics;
- public connector registry discovery;
- stable operation resolution without silent shadowing;
- runtime modes: `check`, `plan`, `execute`, `explain`;
- a minimal real operation set;
- example workflows, example profiles, and golden runtime outputs.

It does **not** yet provide a stable user-facing CLI.

## FILES

- `schema/workflow.schema.json` - workflow schema
- `schema/runtime-result.schema.json` - runtime result schema
- `docs/contracts.md` - stable v0 contract summary
- `examples/` - example workflows
- `profiles/` - example profiles

## WORKFLOW SHAPE

```yaml
version: 0
workflow: inspect-issue

inputs: {}
guards: []
steps: []
```

Rules:

- unknown fields fail validation;
- guards run before effectful steps;
- steps are ordered;
- loaded runtime-facing data stays JSON-shaped.

## PROFILE SHAPE

Profiles are a composition surface, not new connector semantics.

Current profile fields:

- `name`
- `inputs`
- `checks`
- `overrides`

Overrides are explicit and validated. Silent same-name shadowing is not the default behavior.

## PUBLIC CONNECTOR FAMILIES

Current public families:

- `git`
- `gh`
- `shell`

Discoverable operation metadata is available through:

```python
from ordo import get_public_connector_registry

registry = get_public_connector_registry()
contract = registry.to_contract()
```

## CURRENTLY IMPLEMENTED CANONICAL OPERATIONS

Real implementations currently exist for:

- `shell.command`
- `git.clean_worktree`
- `git.branch_not_main`
- `gh.issue.view`

Other public operations may still be registry-visible but return structured not-yet-implemented results if executed.

## RUNTIME MODES

### `check`

Runs validation, profile application, resolution, and guard analysis.

It does not execute effectful business steps.

### `plan`

Returns a machine-readable plan describing:

- which guards are checked;
- which steps are expected;
- blockers;
- whether steps are read-only or effectful;
- whether execution is currently allowed.

### `execute`

Runs steps only after successful validation, resolution, and guards.

Blocked-before-execution remains distinct from execution failure.

### `explain`

Returns structured reasoning about:

- why execution is blocked or allowed;
- which category of problem occurred;
- which blockers are active;
- what the next safe action is, when inferable.

## RESULT SHAPE

Runtime results are JSON-shaped and include at least:

- `mode`
- `status`
- `diagnostics`
- `plan`
- `outputs`
- `operation_results`
- `failed_guard`
- `failed_step`

Main statuses:

- `ok`
- `validation_error`
- `resolution_error`
- `guard_failed`
- `execution_error`

## EXAMPLES

Load and check a workflow:

```python
from pathlib import Path
from ordo import check_workflow, load_workflow_file

workflow = load_workflow_file(Path("examples/inspect-issue.yaml"))
result = check_workflow(workflow)
print(result.to_contract())
```

Discover the public operation surface:

```python
from ordo import get_public_connector_registry

registry = get_public_connector_registry()
for connector in registry.list_connectors():
    print(connector.namespace)
    for operation in connector.operations:
        print(" ", operation.name, operation.kind)
```

## LIMITATIONS

Current v0 limits are important:

- there is no stable CLI yet;
- only a minimal canonical operation set has concrete implementations;
- authoring examples may show composition patterns that go beyond the currently implemented execution surface;
- `${inputs.foo}`-style interpolation is not yet a stabilized execution feature;
- the current surface proves the v0 contract foundation, not broad production connector coverage.

## SEE ALSO

- `README.md`
- `docs/contracts.md`
- `docs/format.md`
- `examples/inspect-issue.yaml`
- `examples/blocked-main-branch.yaml`
- `profiles/backend-default.yaml`
