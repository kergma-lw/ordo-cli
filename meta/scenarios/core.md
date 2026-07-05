# Core scenarios

## Scenario 1: guarded repo ritual

Workflow checks local repo state, confirms guardrails, and executes a small sequence of repo actions.

Expected Ordo value:

- guard barriers are visible before the affected steps run;
- runtime can say whether the ritual is blocked before any business action happens;
- result can tell both human and agent what to fix next.

## Scenario 2: GH-backed issue workflow

Workflow reads GitHub issue/project state through stable `gh.*` operations and composes policy at workflow/profile level.

Expected Ordo value:

- workflow policy is expressed in declarations rather than buried in shell branching;
- connector operations keep stable public semantics while project policy stays local;
- `plan` and `explain` can show issue-state blockers separately from git-state blockers.

## Scenario 3: local project override

Project adds local connector operations or profiles without changing baseline global connector semantics.

Expected Ordo value:

- local adaptation stays explicit;
- reviewers can see where a project extends behavior versus where it consumes shared contracts;
- runtime diagnostics can mention active overrides rather than silently changing behavior.

## Scenario 4: plan before execute

Agent or human asks for `plan`/`explain` before performing effectful steps.

Expected Ordo value:

- runtime returns a machine-readable plan;
- blocked steps are distinguishable from merely not-yet-run steps;
- the caller can decide whether to continue to `execute`.

## Scenario 5: non-git effector

Workflow invokes `shell.*` without assuming git-centric design.

Expected Ordo value:

- shell remains an effector, not the dominant semantic layer;
- explainability still works even when shell is involved;
- the workflow contract remains more stable than opaque shell strings alone.

## Scenario 6: multiple blockers before execution

Workflow is blocked by more than one policy issue at once, for example:

- dirty worktree;
- current branch is `main`;
- issue status is not eligible.

Expected Ordo value:

- `check`/`explain` can surface multiple blockers in one result when safe to do so;
- human does not have to fix issues one-by-one through repeated fail-fast loops;
- agent can choose the safest next question or remediation.

## Scenario 7: policy-heavy close-task ritual

Workflow for shipping/closing a task depends on repo kind, verification profile, git safety checks, and issue/project state.

Expected Ordo value:

- repo-specific verification can be selected via profiles without hiding the high-level ritual intent;
- runtime can explain why merge/close is blocked before attempting side effects;
- final result can show which checks passed, which were skipped, and which blocked execution.

## Scenario 8: agent asks what is allowed now

Agent inspects a repo and asks what action is currently safe:

- only check;
- plan available but execute blocked;
- execute allowed.

Expected Ordo value:

- runtime status is explicit enough to drive agent behavior;
- no brittle parsing of shell logs is required;
- decision support is part of the runtime contract, not an afterthought.

## Scenario 9: explainable failure, not just execution failure

User wants to know not only that a workflow failed, but whether it:

- failed validation;
- failed resolution;
- was blocked by guards;
- failed during step execution.

Expected Ordo value:

- these categories remain distinct in the result surface;
- user and agent get a clearer recovery path;
- the project stays different from a generic step runner that mainly exposes logs and exceptions.
