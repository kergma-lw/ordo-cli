# Workflow data shape

## Stable top-level fields

- `version`
- `workflow`
- `inputs`
- `state_needs`
- `guards`
- `steps`

## Stable guard shape

```yaml
- uses: namespace.name
  with: {}
```

## Stable logical state need shape

```yaml
state_needs:
  task_memory: {}
```

The initial stable shape is marker-only.

Implications:

- each logical state role name maps to an empty object;
- additional per-need fields are not part of the initial stable contract;
- unknown nested fields under a logical state need fail validation.

## Stable step shape

```yaml
- name: some-step
  uses: namespace.name
  with: {}
```

Built-in runtime state mutation forms may also appear in `steps`.

Stable state target/read path grammar:

```text
state.<role>[inputs.<key-reference>][.<field>...]
```

Rules:

- reads use this path only inside `${...}`;
- `state_set` keys use this path text directly;
- `state_delete` uses this path text directly;
- the key reference inside `[...]` must use dotted `inputs...` form;
- post-key field traversal uses dotted identifiers only.

Set example:

```yaml
- name: remember-branch
  state_set:
    state.task_memory[inputs.task_key].branch: ${inputs.branch}
```

Delete example:

```yaml
- name: forget-branch
  state_delete: state.task_memory[inputs.task_key].branch
```

Workflow files do not declare runtime state locations themselves.
They declare logical state needs and reference them through the `state.<role>...` read and mutation surface.

Unsupported or ambiguous variants are outside the initial stable contract.

## Current rule

Unknown top-level and nested stable fields fail validation.

## Serialization rule

- Workflow files may be authored in YAML.
- Workflow semantics are defined over the loaded data model, not over YAML-specific syntax.
- Stable workflow data must be representable as a losslessly JSON-serializable structure after loading.
- YAML-specific mechanisms such as anchors, aliases, tags, or merge behavior must not introduce distinct runtime semantics unless explicitly standardized.
