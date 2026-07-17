# Playbook data shape

## Stable top-level fields

- `version`
- `states`
- `workflows`
- `profiles`
- `defaults`

## Stable workflow entry shape

```yaml
workflows:
  close-task:
    file: close-task.yml
    working_directory: ${inputs.repo_root}
    state_bindings:
      task_memory: repo_task_state
```

Required field:

- `file`

Optional stable field:

- `working_directory`
- `state_bindings`

## Stable pre-run shape

```yaml
pre_run:
  - workflows/resolve-context.yml
  - workflows/ensure-environment.yml
```

Optional stable top-level field:

- `pre_run`

Stable `state_bindings` shape:

```yaml
state_bindings:
  task_memory: repo_task_state
```

## Stable defaults shape

```yaml
defaults:
  profile: backend-default
  working_directory: repos/default-backend
```

Optional stable field:

- `profile`
- `working_directory`

## Stable profile entry shape

```yaml
profiles:
  backend-default:
    file: backend-default.yml
```

Required field:

- `file`

## Stable state entry shape

```yaml
states:
  task_state:
    path: .ordo/state/task-state.json
```

Required field:

- `path`

## Serialization rule

- Playbook files may be authored in YAML.
- Playbook semantics are defined over the loaded data model, not over YAML-specific syntax.
- Stable playbook data must be representable as a losslessly JSON-serializable structure after loading.
- YAML-specific mechanisms such as anchors, aliases, tags, or merge behavior must not introduce distinct runtime semantics unless explicitly standardized.

## Current rule

Unknown top-level and nested stable fields fail validation.
