# Connector requirements

## Public connector contract

- A workflow must reference stable public connector operations.
- The initial fixed connector domains are `git`, `gh`, and `shell`.
- Connector resolution must preserve stable public semantics independent of local implementation details.
- Project-local profiles and overrides must not silently change the public meaning of a referenced global connector operation.
- Connector operation kinds fixed so far are `probe` and `action`, and they exist only inside connector families.

## Connector result discipline

- Every connector operation must return a structured result on both success and failure paths.
- Every connector operation must preserve that structured result contract even when internal exceptions occur.
- Every connector operation must support narrow local explainability of its own outcome.
- A successful `probe` result must contain meaningful observations or diagnostics, not only a bare success flag.
- A successful `action` result must contain a meaningful effect summary or diagnostics, not only a bare success flag.
- Raw stdout/stderr, when produced by an implementation, must be treated as optional detail fields rather than the primary contract surface.

## Extension boundary

- The system must allow project-local extension without forking the global contract.
- Project-specific policy must compose over stable connector operations instead of mutating their meaning.

## Probe addition policy

- Public probes should default to exposing stable observable facts rather than workflow-specific policy verdicts.
- Workflow policy should prefer composition in guard expressions over growth of specialized probe names.
- A new public probe should be added only when at least one of the following is true:
  - it exposes a stable fact that is not otherwise available through existing probe outputs;
  - repeated workflow composition would otherwise require awkward normalization in many places;
  - the needed condition would otherwise force guard-expression language growth beyond compact reviewable policy;
  - the needed condition would otherwise expose unstable operational detail that should remain inside the connector contract.
- A proposed public probe should be rejected when its primary value is merely to avoid a simple comparison or boolean composition in workflow guards.
- Public probe names should avoid encoding local policy, approval decisions, or workflow intent when those can be expressed as guard composition over existing probe results.

## Canonical git probe set

- The canonical `git` probe set should remain small and orthogonal.
- The current target set for broad repo-state coverage is:
  - `git.repo`
  - `git.branch`
  - `git.branches`
  - `git.worktree`
  - `git.worktrees`
  - `git.stash`
  - `git.state`
  - `git.ref(ref=...)`
  - `git.upstream`
  - `git.range(base=..., head=...)`
- This set should be preferred over adding many narrower git probes for local rituals.
- Older specialized policy-shaped probes should not be used as the preferred long-term public surface when the same intent can be expressed through canonical git facts and guard composition.
