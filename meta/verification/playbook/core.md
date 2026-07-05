# Playbook verification

## Rule

Playbook must provide a deterministic and reviewable project-local launch surface.

## Checks

- `.ordo/playbook.yml` discovery behavior is documented and testable.
- Missing playbook, missing workflow entry, and missing profile entry fail with distinct structured outcomes.
- Workflow names are unique within the playbook workflow catalog.
- Profile names are unique within the playbook profile catalog.
- State names are unique within the playbook state catalog.
- Workflow state-binding role names are unique within a workflow entry.
- Relative workflow, profile, and state paths resolve deterministically from playbook-owned context.
- Launch-time input overrides, when supported, deterministically override workflow and profile input defaults for one run only.
- Workflow logical state roles resolve deterministically to declared playbook state entries.
- Every declared workflow logical state role has a binding in the active playbook workflow entry.
- No playbook workflow entry provides extra state bindings for undeclared workflow logical state roles.
- No silent fallback resolves a missing named workflow or profile to an arbitrary nearby file.
- Workflow business logic remains in workflow files rather than being duplicated as playbook-only execution semantics.
