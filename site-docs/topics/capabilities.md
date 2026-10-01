# Capabilities

Check whether a workflow surface is supported before relying on it.

Use the boundary and restriction explanations before choosing an authoring shape.

## Workflow step forms

- Use `run` to invoke a named reusable target. For short local repeated work, pair `for_each` with inline `steps`; keep larger, reusable, or guarded repeated work behind `run`.
- Use `profile_switch` to select another declared profile for later work on the current path. Use `result` for one ordered result value and `publish` for a named caller-facing payload.
- Use `with` to pass explicit runtime values to a `uses` operation or `run` target. A run target reads its values as `args.name`; `include.with` instead binds source-time fragment arguments.
- An include binding is evaluated in the caller context and may read caller inputs, the current item, state, or an earlier registered step output. The expanded fragment receives only values declared as `args.name`.
- `ordo-help describe workflow.step.run`: Invoke a named reusable target
- `ordo-help describe workflow.step.steps`: Define a short inline repeated body
- `ordo-help describe workflow.step.profile_switch`: Change the profile for later work
- `ordo-help describe workflow.step.result`: Append one ordered result value
- `ordo-help describe workflow.step.publish`: Publish a caller-facing payload
- `ordo-help describe workflow.step.with`: Pass operation or run-target values

## Published surfaces



### Local expressions

This surface is supported.



### Representation adapters

This surface is supported.



### State bindings

This surface is supported.



### State needs

This surface is supported.



### State set step

This surface is supported.



### State delete step

This surface is supported.



### Value step

This surface is supported.



### Included fragments

This surface is supported.



### Legacy launchers

This surface is deprecated.



#### Do not infer

- launcher support means launcher-centric workflow authoring is still preferred
- a launcher is safer than a published routine by default

### Legacy launcher step

This surface is deprecated.



#### Do not infer

- step-level launcher selection is a preferred new authoring path
- launchers should be chosen over routine publication for new project-local automation

### Step conditions

This surface is supported.



#### Do not infer

- one shared boolean condition surface means if and gate do the same semantic job
- if is the catch-all control mechanism for applicability, admission, and local branching

### Registered step output

This surface is supported.



### Step outputs

This surface is supported.



#### Do not infer

- step outputs are ambient global context instead of explicit reads from named or registered steps

### Workflow branching

This surface is supported.



#### Do not infer

- branching support means if should carry workflow applicability or admission decisions
- workflow branching is best modeled by stretching if across every conditional concern

## Restrictions



### Guards cannot read step output

Registered step references are not allowed in guard expressions



#### Why

- guards run before effectful step execution and therefore cannot depend on registered step results

### Guard adapters are read-only

Representation-adapter write paths such as '->...' are not allowed in guard expressions



#### Why

- guard expressions may use read-only local-expression constructs but must remain pure and pre-execution-safe

### Guards need boolean decisions

Guard expressions must evaluate to a boolean result



#### Why

- guard success and failure are defined by boolean policy outcomes rather than arbitrary value production

### Steps use one primary form

A workflow step must define exactly one of uses, run, steps, profile_switch, value, result, publish, state_set, or state_delete; a standalone gate checkpoint is the exception



#### Why

- primary step forms are mutually exclusive in the workflow contract

### Use with only for invocations

The with field is allowed only together with uses or run



#### Why

- runtime value inputs belong to operation-call and named-run step forms

### Use launchers only for operation calls

The launcher field is allowed only together with uses



#### Why

- launcher selection wraps operation-call execution surfaces rather than builtin value or state steps

### Register only result-producing steps

The register field is allowed only together with uses, run, or value



#### Why

- Only operation-call steps, reusable run invocations, and value steps produce results that can be named for later reads

### Optional steps cannot register results

The if and register fields cannot be used together



#### Why

- A skipped optional step has no result to name for later reads

### Gated steps cannot register results

The gate and register fields cannot be used together; split the gate into a standalone checkpoint step before the registered step



#### Why

- gate admission should stay separate from step-result publication so blocked steps never need to imply a registered output surface

### Read results from earlier steps

Registered step references may target only earlier steps in the same workflow



#### Why

- step-result reads are order-sensitive execution-local data flow rather than random access workflow state

### Write one state target per step

state_set must contain exactly one target entry



#### Why

- each state-set step writes one resolved state target at a time

### Included fragments cannot access state

Included fragments must not read, declare, or mutate runtime state



#### Why

- runtime state remains a top-level workflow handoff surface rather than reusable fragment-local memory

### Write a state role after its last read

Before binding, logical state role writes and deletes are allowed only after the final read of that same role; bound validation instead compares actual storage in each access context



#### Why

- persistent runtime state should capture final cross-run handoff rather than per-run scratch flow

### Write storage after its final read

After binding, write or delete only after the final read of the same actual file, regardless of role, state name, profile, key, or field



#### Why

- relative paths resolve in each access context; normalized paths, symlinks, and existing hardlinks can alias, while the same role may resolve to different files and be valid

### Establish storage identity before conflicting access

Conservatively reject early only relevant write/later-read pairs whose storage identity cannot be established; this is not a proven ordering violation



#### Why

- Checks happen before observations and effects, so uncertain context alone does not reject read-only, read-before-write, or known-disjoint access. Checking one child workflow does not establish safety across separate calls or repeated work.

### Formatting arguments are a list

format-object args must be a list when provided



#### Why

- format object arguments are evaluated positionally
