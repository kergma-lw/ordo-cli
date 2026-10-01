# Use declared runtime profile

You are reading or migrating older workflow logic that still invokes runtime.profile.use directly.

Legacy runtime action for switching later execution in the current run to another declared profile.

## Use when

- An existing compatibility workflow must switch profiles for later steps before it can be migrated to the workflow-native form.

## What to provide

- `profile`: required; provide the name of a profile already declared for this run. This action does not create or discover profiles.

## Result and boundary

- Later execution in the current run uses the selected profile and returns it as `profile`.
- This legacy action changes only later work in the current run. Replace it with the workflow profile-switch form during migration; it does not retroactively change earlier work or a fixed workflow profile.

## Do not use for

- New profile-switch authoring; use workflow.step.profile_switch instead of a legacy runtime action call.
- Declaring a fixed workflow-owned profile binding; use workflow.profile when the subtree should always start under one profile.

## Related references

Use these related references when you need a neighboring operation or more context.


- `ordo-help describe connector.runtime`: Parent runtime connector family
- `ordo-help describe workflow.step.profile_switch`: Preferred workflow-native step surface that replaces this legacy action
- `ordo-help describe workflow.profile`: Workflow field for fixed project-local profile binding before guards run

## Examples

- runtime.profile.use with inputs {"profile": "frontend"}

## Inspect next

- workflow.step.profile_switch
- workflow.profile
- profile.name

## Exact machine contract

Use `ordo-help operation runtime.profile.use --json` when you need the exact machine-readable input and result contract for this operation.
