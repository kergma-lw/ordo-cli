# Authoring scenarios

## Human authoring

Human writes or reviews a workflow using readable connector operations, small schema surface, and examples.

Human should be able to answer, by reading the declaration:

- what policy is enforced;
- which guards can block execution;
- which steps are intended if guards pass;
- whether shell is being used as an escape hatch or as the main hidden mechanism.

## Agent authoring

Agent writes a workflow against schema + examples + connector contracts and can predict validation/runtime behavior.

This is not a marginal scenario. It is one of the main intended ways the product is used.

Agent should be able to predict:

- whether `uses` references are valid and resolvable;
- what `check` and `plan` would return in broad shape;
- what categories of failure are possible;
- which result codes are safe to branch on programmatically.

Agent should also be able to determine that the better next step is to compose an existing workflow/profile from public operations rather than invent a new connector operation.

## Mixed maintenance

Human and agent can evolve the same workflow without hidden local semantic traps.

This implies:

- local overrides stay explicit;
- public operation semantics stay stable;
- workflow meaning does not silently drift into implementation details only a shell expert can reconstruct.

## Review scenario

Reviewer should be able to tell whether a proposed workflow is:

- a clear declaration of policy and intent;
- an opaque shell script disguised as YAML;
- safe for an agent to invoke in `check`/`plan` mode.

## Composition-first scenario

Agent needs a new local ritual.

Preferred path:

- inspect available public operations and examples;
- compose a workflow from existing operations;
- add or adjust a profile when local policy or defaults differ;
- run machine-checkable validation and explanation before any execution.

Discouraged default path:

- invent a new connector family or new public operation semantics just to express routine local variation.

## Explainability scenario

Both human and agent should be able to use runtime explanation without replaying failure manually.

Desired experience:

- reviewer asks "why is this blocked?" and gets a structured answer;
- agent asks "what can I safely do next?" and gets machine-readable status plus next actions;
- explanation quality does not depend on scraping unstructured stderr.
