# Workflow data shape

## Stable top-level fields

- `version`
- `workflow`
- `inputs`
- `states`
- `guards`
- `steps`

## Stable guard shape

```yaml
- uses: namespace.name
  with: {}
```

## Stable step shape

```yaml
- name: some-step
  uses: namespace.name
  with: {}
```

Built-in runtime state mutation forms may also appear in `steps`.

Set example:

```yaml
- name: remember-branch
  state_set:
    states.task_state[inputs.issue_ref].branch: ${inputs.branch}
```

Delete example:

```yaml
- name: forget-branch
  state_delete: states.task_state[inputs.issue_ref].branch
```

## Stable state declaration shape

```yaml
states:
  task_state: .ordo/task-state.json
```

## Current rule

Unknown top-level and nested stable fields fail validation.

## Serialization rule

- Workflow files may be authored in YAML.
- Workflow semantics are defined over the loaded data model, not over YAML-specific syntax.
- Stable workflow data must be representable as a losslessly JSON-serializable structure after loading.
- YAML-specific mechanisms such as anchors, aliases, tags, or merge behavior must not introduce distinct runtime semantics unless explicitly standardized.
