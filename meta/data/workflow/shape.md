# Workflow data shape

## Stable top-level fields

- `version`
- `workflow`
- `inputs`
- `state_needs`
- `blocks`

Compatibility-only top-level fields:

- `guards`
- `steps`

The stable execution shape is block-based.
Top-level `guards` and `steps` remain compatibility inputs that normalize to `blocks`.

## Stable block shape

```yaml
blocks:
  - guards:
      - git.worktree.clean
  - steps:
      - name: verify
        uses: shell.run
        with: {}
```

Rules:

- `blocks` is an ordered non-empty list;
- each block item must declare exactly one of `guards`, `steps`, or `include`;
- `guards` block value is a non-empty guard list;
- `steps` block value is a non-empty step list;
- an `include` block item references one included workflow fragment and may optionally bind `with` values for declared fragment `args`;
- block order is semantically meaningful;
- a `guards` block is evaluated before any later `steps` block may run.

Current stable shape note:

- `run` is not part of the current stable block shape.
- A future invocation-oriented step form may add `run` under `steps:` rather than changing the meaning of existing `include` items.

Stable include item form:

```yaml
- include: github/check-issue
  with:
    repository: ${inputs.repository}
    issue_number: ${inputs.issue_number}
```

Include item rules:

- `include` is a non-empty string reference to an included workflow fragment;
- `with` is optional and, when present, is an object;
- `with` keys bind only declared fragment `args` keys;
- include expansion preserves block order in the assembled workflow.

## Planned fragment run step shape

Illustrative future form:

```yaml
- steps:
    - name: comment-and-status
      run: github/comment-and-set-status
      if: ${step.issue.outputs.open}
      with:
        comment: "Issue is open."
        status: "In Progress"
```

Planned run step rules:

- `run` would be a non-empty reusable-fragment reference on one step entry;
- `name` would remain required because the author-facing surface still treats the invocation as one step;
- `with` would remain the explicit fragment-argument binding object;
- `if` would be evaluated in caller scope rather than in fragment-body scope;
- the invoked fragment would execute with its own fragment-local `args...` and `step...` scope.

## Included fragment document shape

Illustrative included fragment file:

```yaml
description: Check one issue and reuse the loaded result
args:
  repository: string
  issue_number:
    type: integer
  project_id:
    type: string
    default: null
  dry_run:
    type: boolean
    default: false

blocks:
  - steps:
      - name: inspect
        uses: gh.issue
        with:
          repository: ${args.repository}
          issue_number: ${args.issue_number}
```

Rules:

- an included fragment may declare `description`;
- an included fragment may declare `args` as a mapping of fragment-local argument names;
- an `args` entry may use a short scalar declaration such as `repository: string` for a required argument;
- an `args` entry may use an object declaration with fields such as `type`, `required`, and `default`;
- `default` may be any JSON-shaped value, including `null`;
- an omitted optional argument and an explicit `null` binding are distinct authoring cases;
- fragment-local argument reads use the `args.<name>` surface;
- included fragment payload content must still normalize to ordinary workflow block semantics after argument binding and expansion.

## Compatibility normalization

Illustrative legacy form:

```yaml
guards:
  - git.worktree.clean

steps:
  - name: verify
    uses: shell.run
    with: {}
```

Normalized form:

```yaml
blocks:
  - guards:
      - git.worktree.clean
  - steps:
      - name: verify
        uses: shell.run
        with: {}
```

Normalization rules:

- if `blocks` is present, top-level `guards` and top-level `steps` must not be present;
- if `blocks` is absent, at least one of top-level `guards` or top-level `steps` must be present;
- top-level `guards` normalizes to one leading `guards` block;
- top-level `steps` normalizes to one trailing `steps` block.

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
