# Playbook routine requirements

## Role

- A project may publish a routine registry as a project-local invocation catalog for bounded local automation.
- The routine registry must remain a playbook-adjacent launch surface rather than a second workflow language or a hidden connector layer.
- Routines must be project-local and must not redefine stable public connector semantics.

## Discovery and publication

- The default routine-registry discovery path must be deterministic and reviewable.
- The initial default routine-registry path may be `.ordo/routines.yaml`.
- A routine registry must fail clearly when missing, malformed, or structurally invalid.
- Routine identifiers must be unique within the registry.
- Workflow use sites must reference routines only by declared identifier.
- A routine registry must not implicitly publish arbitrary repository scripts by directory scanning alone.

## Invocation contract

- A workflow routine invocation must accept only a declared routine identifier and declared routine arguments.
- Workflow use sites must not embed arbitrary command text as the routine invocation surface.
- Each routine must declare its invocation kind as either `probe` or `action`.
- Each routine must declare its accepted arguments explicitly enough for validation before effectful execution.
- Extra routine arguments that are not declared by the routine contract must fail validation.
- Missing required routine arguments must fail validation.

## Output discipline

- A routine result must be compact and structured.
- Full stdout/stderr logs must not be returned inline as the primary contract surface.
- Runtime may preserve complete routine logs in runtime-owned temporary artifacts such as `/tmp`, but those artifacts are secondary detail rather than the primary result payload.
- A routine result should expose a short summary and a bounded diagnostic excerpt or highlight surface when useful.
- A routine result must preserve the distinction between contract-level non-success and exceptional execution breakdown.

## Probe routines

- A routine declared as `probe` must be intended as observational rather than effectful.
- A probe routine should declare a structured observation output contract whenever its primary value is returned data rather than only a pass/fail verification verdict.
- Probe routines that primarily perform verification may publish a compact verification verdict plus bounded excerpts rather than large raw logs.
- A probe routine must not rely on unbounded prose stdout as its only meaningful observation contract.

## Action routines

- A routine declared as `action` must be treated as effectful even when its implementation happens to be a local helper script.
- Action routines should expose honest local failure classes rather than only a generic nonzero exit narrative.
- Action routines must not be presented as probes merely because they are convenient to run during checks.

## Product boundary

- Routines are a bounded opaque local-automation surface.
- Routines must not become the preferred permanent home for semantics that belong in reusable connector families.
- When a stable cross-project domain model exists, that model should prefer connector publication over indefinite routine accretion.
- Routine implementation may be restricted to an explicit project-owned publication area such as `.ordo/scripts/` so the registry does not silently adopt arbitrary repository history as workflow surface.
