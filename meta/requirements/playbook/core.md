# Playbook requirements

## Discovery and launch surface

- A project-local playbook must be discoverable through a deterministic default location.
- The default discovery rule must be simple enough for both humans and agents to predict without trial-and-error.
- Playbook discovery failure must produce a structured and reviewable error rather than an implicit fallback to unrelated files.
- An explicit playbook path must override default discovery when the caller provides one.

## Catalog and composition

- A playbook must support named workflow entries as the primary launch surface.
- A playbook may support named profile entries for launch-time selection and defaults.
- A playbook launch surface may support explicit launch-time input overrides for one run.
- A playbook launch surface may declare an explicit execution working directory for a run through playbook defaults, the active profile, or the active workflow entry.
- Working-directory precedence must be deterministic and follow increasing specificity from playbook defaults to profile context to workflow-entry context.
- Any declared playbook-, profile-, or workflow-level working directory may use the existing `${...}` value-expression syntax when the expression stays within an activation-time-safe subset.
- A playbook may declare a `pre_run` workflow set that executes before the requested workflow in the same runtime session.
- A `pre_run` workflow set must remain explicit, project-local, and reviewable from the playbook surface.
- Failure in any `pre_run` workflow must prevent effectful execution of the requested workflow.
- A playbook must support named runtime state declarations for project-local reuse.
- A playbook must support binding workflow logical state roles to named project state declarations.
- Every workflow logical state need must have an explicit playbook binding for the active workflow entry.
- Every playbook state binding must target an existing named playbook state declaration.
- Playbook must fail validation when a workflow entry contains a state binding for an undeclared workflow logical state need.
- Playbook-owned names must be unique within their own catalogs.
- Playbook composition must remain explicit rather than relying on silent shadowing or broad filename guessing.

## Resolution discipline

- Relative workflow and profile references must resolve deterministically from playbook-owned context.
- An execution working directory must not change playbook discovery or reference resolution rules.
- A working-directory expression must be fully resolvable before the first guard or step executes.
- Named references must either resolve to one declared target or fail clearly.
- Missing catalog targets must fail validation before effectful execution starts.
- Unknown stable fields in the playbook contract should fail validation.

## Product boundary

- A playbook must remain a project-level launch surface rather than becoming a second workflow language.
- Workflow business logic should stay in workflow files rather than being duplicated into playbook entry definitions.
- Playbook ergonomics should reduce the need for handwritten bootstrap commands without hiding runtime semantics.
- Execution working directory should remain explicit runtime context rather than hidden shell-first behavior.
- A working-directory expression must reuse the documented value-expression syntax rather than introducing a second expression language.
- A working-directory expression must not read runtime state, registered step results, or any runtime-derived value that is unavailable at launch time.
