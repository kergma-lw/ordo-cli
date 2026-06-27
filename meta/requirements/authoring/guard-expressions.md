# Authoring requirements for guard expressions

## Compactness

- Guard authoring must support compact declaration of execution conditions.
- Routine policy should usually be readable in a short guard list without requiring a screen of repetitive structural boilerplate.
- A compact guard surface is a core product quality because Ordo exists in part to replace difficult-to-review shell guard logic.

## Discoverability

- An author must be able to tell which parts of a guard expression are public probe invocations and which parts are comparisons over probe results.
- A plain string item in `guards` should be the preferred compact authoring form for expression guards.
- The object form with `uses` should remain available where an explicit operation call is clearer or needed for compatibility.
- Zero-argument probe references should not require empty call syntax when no arguments are being passed.
- Parameterized probe references should remain visually distinct enough that an author can tell inputs are being supplied.
- Workflow input references should be readable as `inputs.name` rather than requiring a template interpolation surface.
- Named arguments should be the preferred authoring form for parameterized probe calls.
- Boolean-valued probe fields should be usable directly as conditions without requiring redundant `== true` boilerplate.

## Preferred authoring surface

- A zero-argument probe reference should read like a compact fact, for example `git.worktree.clean` or `git.branch`.
- A parameterized probe reference should prefer a compact meta-style call surface, for example `gh.issue(issue=inputs.issue).status`.
- The authoring surface should prefer a minimal and orthogonal public probe vocabulary over many specialized policy-encoded probe names.

## Checkability

- Guard expressions must remain machine-checkable and agent-checkable before execution.
- Validation and diagnostics should point to the failing expression segment rather than only reporting a generic guard failure.
- Expression syntax should remain small enough that an agent can learn it from contract docs and examples without treating the workflow format as a hidden programming language.
