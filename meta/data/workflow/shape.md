# Workflow data shape

## Stable top-level fields

- `version`
- `workflow`
- `inputs`
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

## Current rule

Unknown top-level and nested stable fields fail validation.

## Serialization rule

- Workflow files may be authored in YAML.
- Workflow semantics are defined over the loaded data model, not over YAML-specific syntax.
- Stable workflow data must be representable as a losslessly JSON-serializable structure after loading.
- YAML-specific mechanisms such as anchors, aliases, tags, or merge behavior must not introduce distinct runtime semantics unless explicitly standardized.
