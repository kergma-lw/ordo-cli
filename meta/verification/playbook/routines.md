# Playbook routine verification

## Rule

Routine publication must provide a bounded and reviewable project-local invocation surface.

## Checks

- `.ordo/routines.yaml` discovery behavior is documented and testable when routine publication is enabled.
- Missing or malformed routine registry fails with a structured outcome rather than a silent fallback to arbitrary shell execution.
- Routine identifiers are unique.
- Unknown routine identifiers fail validation before effectful execution.
- Missing required routine arguments fail validation.
- Extra routine arguments fail validation.
- Routine-call environment bindings remain explicit and reviewable rather than arising from automatic mirroring of all workflow inputs.
- Workflow-authored routine environment bindings reject malformed or unsupported reference paths and other structurally invalid shapes.
- Routine environment-variable names are generated predictably from the forwarded reference path.
- Routine environment bindings fail when the referenced value is non-scalar rather than silently serializing structured data.
- Routine invocations do not accept inline arbitrary command text at the workflow use site.
- Probe routines do not rely on unbounded raw stdout as their only meaningful observation contract.
- Full routine logs are preserved outside the primary payload rather than returned inline by default.
- Routine publication remains project-local and does not silently redefine reusable connector semantics.
