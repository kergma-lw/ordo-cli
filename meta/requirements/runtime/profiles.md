# Runtime profile requirements

## Profile purpose

- The runtime must treat a profile as a named operational context for one playbook run.
- A profile must not act as an undocumented second workflow language.
- Profile application must remain explicit in runtime-facing outputs.
- Overrides introduced through profile-owned context must remain explicit rather than silently changing workflow meaning.

## Reviewability

- The active profile must be identifiable in structured runtime outputs.
- Inputs contributed by the active profile must remain inspectable and attributable.
- Execution-affecting profile behavior must be reviewable from playbook material rather than hidden in implementation-only defaults.

## Allowed scope

- Profiles may supply runtime-facing activation context such as inputs and approved overrides.
- Profiles may supply execution-location context through a profile-scoped `working_directory` declaration when the public model allows it.
- Profiles may supply connector-scoped ambient execution context through a profile-owned `connectors` mapping.
- Profile-owned connector context must be delivered as raw family-scoped bootstrap input rather than as ordinary workflow-readable data or ad hoc operation-local overrides.
- Connector bootstrap must remain the only layer that interprets raw profile-owned connector context directly.
- Profiles may contribute bounded ambient execution context to routine invocations only when workflow material explicitly forwards profile-carried values through a reviewable routine environment surface.
- When both playbook defaults and profile-level working-directory declarations are present, profile-level declaration must win unless the active workflow entry supplies a more specific working-directory declaration.
- Future runtime-scoped execution wrappers or launchers, if standardized, should attach through profiles or workflow entries rather than through hidden global process state.
- When profiles participate in launcher selection, that participation must remain explicit enough for a reviewer to see which execution wrapper context is active.
- New profile authoring should prefer routine-compatible execution context over launcher-specific wrapper setup whenever the workflow can move to a published routine surface instead.
- Runtime profile switching should be represented by an engine-level construct such as `profile_switch`, not by an ordinary connector action.
- `profile_switch` must change only subsequent execution context within the current run unless the public model later standardizes stronger semantics.
- `profile_switch` should apply the newly active profile's input defaults to subsequent steps using the same missing-input discipline as activation-time profile application.
- `profile_switch` must not depend on `step.*` outputs or other post-step execution knowledge.

## Constraints

- Profiles must not silently replace workflow intent with unrelated behavior.
- Profile-provided execution context must remain declarative enough for normal runtime activation and failure handling.
- When a profile changes execution context, runtime results should preserve which context was selected and why it matters.
- Profile-owned connector context must not become ordinary workflow-readable expression context by default.
- Profile-owned connector context must not bypass connector bootstrap by becoming raw operation-visible launch material.
- Profile-provided ambient routine context must remain bounded and must not implicitly project the full profile-resolved workflow input namespace into routine environments.
- Profile switching must not silently reinterpret an already-activated workflow run under a different profile.
- Profile switching must not override explicit activation inputs that were already provided for the current run.
- Same-name shadowing of base connector operations must not be default behavior for profile-owned adaptation.
- `check` may apply deterministic `profile_switch` transitions statically when their target profile is resolvable from pre-execution knowledge.
