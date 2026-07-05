# Runtime profile requirements

## Profile purpose

- The runtime must treat a profile as a named operational context for one playbook run.
- A profile must not act as an undocumented second workflow language.
- Profile application must remain explicit in runtime-facing outputs.

## Reviewability

- The active profile must be identifiable in structured runtime outputs.
- Inputs contributed by the active profile must remain inspectable and attributable.
- Execution-affecting profile behavior must be reviewable from playbook material rather than hidden in implementation-only defaults.

## Allowed scope

- Profiles may supply runtime-facing activation context such as inputs and approved overrides.
- Profiles may supply execution-location context when the public model allows it, for example through workflow-entry `working_directory` expressions.
- Future runtime-scoped execution wrappers or launchers, if standardized, should attach through profiles or workflow entries rather than through hidden global process state.
- When profiles participate in launcher selection, that participation must remain explicit enough for a reviewer to see which execution wrapper context is active.

## Constraints

- Profiles must not silently replace workflow intent with unrelated behavior.
- Profile-provided execution context must remain declarative enough for `check`, `plan`, and `explain` to report it.
- When a profile changes execution context, runtime results should preserve which context was selected and why it matters.
