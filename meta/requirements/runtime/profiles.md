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
- Profiles may supply execution-location context through a profile-scoped `working_directory` declaration when the public model allows it.
- When both playbook defaults and profile-level working-directory declarations are present, profile-level declaration must win unless the active workflow entry supplies a more specific working-directory declaration.
- Future runtime-scoped execution wrappers or launchers, if standardized, should attach through profiles or workflow entries rather than through hidden global process state.
- When profiles participate in launcher selection, that participation must remain explicit enough for a reviewer to see which execution wrapper context is active.
- Runtime profile switching should be represented by an engine-level construct such as `profile_switch`, not by an ordinary connector action.
- `profile_switch` must change only subsequent execution context within the current run unless the public model later standardizes stronger semantics.
- `profile_switch` should apply the newly active profile's input defaults to subsequent steps using the same missing-input discipline as activation-time profile application.
- `profile_switch` must not depend on `step.*` outputs or other post-step execution knowledge.

## Constraints

- Profiles must not silently replace workflow intent with unrelated behavior.
- Profile-provided execution context must remain declarative enough for `check`, `plan`, and `explain` to report it.
- When a profile changes execution context, runtime results should preserve which context was selected and why it matters.
- Profile switching must not silently reinterpret an already-activated workflow run under a different profile.
- Profile switching must not override explicit activation inputs that were already provided for the current run.
- `check` may apply deterministic `profile_switch` transitions statically when their target profile is resolvable from pre-execution knowledge.
