# Runtime requirements

## Runtime behavior

- The runtime must support at least `review`, `check`, `plan`, `execute`, and `explain`.
- The runtime must return structured results, not only raw stdout/stderr.
- `plan` must describe what would be checked and executed, including known blockers.
- `explain` must return runtime reasoning in a structured form, not merely debug logs or traceback text.
- The runtime must distinguish at least validation failure, resolution failure, guard failure, execution failure, and success.
- Structured results must be usable by both a human reviewer and an automated agent without log scraping.
- Runtime diagnostics should prefer normalized categories and structured fields over ad hoc human prose.
- At minimum, the structured runtime result must preserve a human-readable message and a machine-readable code when non-success detail matters.
- The model should support fail-safe behavior for local operational rituals where risk reduction matters more than maximum flexibility.
- The runtime must expose a machine-usable decision surface, not only an execution surface.

## Runtime serialization requirements

- Structured runtime results must be losslessly JSON-serializable.
- `check`, `plan`, `execute`, and `explain` outputs must be consumable without log scraping or YAML parsing.
- Diagnostics, plan items, blockers, inferred next actions, and other contract-level runtime surfaces must be encoded as JSON-shaped fields rather than only human prose.
- Human-readable text may supplement runtime results, but it must not be the only carrier of machine-relevant meaning.

## Agent-facing decision support

- The runtime must be able to answer, in machine-readable form:
  - what is known now;
  - whether execution is allowed now;
  - why execution is blocked when blocked;
  - what next safe action is available when it can be inferred safely.
- `review`, `check`, `plan`, and `explain` must remain baseline decision-support modes rather than optional UX sugar around `execute`.

## Explainability

- The system must be able to answer "why is this workflow blocked?" without requiring execution of business steps.
- The system must be able to answer "what would happen if this workflow executed now?" in a machine-readable plan/result shape.
- The system must preserve the difference between:
  - blocked before execution;
  - execution intentionally skipped;
  - execution attempted and failed.
- When a step is intentionally skipped because its `if` condition evaluated to `false`, runtime outputs should preserve that reason in machine-usable form.
- When a step `if` condition cannot be evaluated, the runtime must fail execution rather than silently treating the condition as `false`.
- `explain` output should include useful next actions when the runtime can infer them safely.
- The explanation surface must remain stable enough for agent tooling to rely on status codes and categories.
- If the product later adds bounded `for_each` on `run`, `check`, `plan`, and `explain` must preserve statically knowable fan-out facts such as whole-step eligibility, exact cardinality when knowable, and explicit unknown-cardinality state when not knowable before execution.
- If bounded `for_each` is later added on `run`, the runtime must preserve the difference between a fan-out step blocked before expansion, a fan-out step statically expanded with known item count, and a fan-out step whose item count remains runtime-only.
