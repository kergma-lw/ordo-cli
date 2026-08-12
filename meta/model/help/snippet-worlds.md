# Help snippet worlds

## Role

- A snippet world is a named, stable teaching context for help-example publication and verification.
- Snippet worlds exist for `ordo-help` discovery surfaces rather than for workflow runtime semantics.
- A snippet world is a help-model concept, not a workflow feature.

## Why snippet worlds exist

- Many help snippets are too small to stand alone as full workflows.
- Value-only examples are precise, but they are often weak imitation material for authors.
- Full authoring fragments are more useful for imitation, but they need shared context to remain strictly verifiable.
- One-off harnesses do not scale well and make examples harder to compare across help surfaces.

Snippet worlds exist to let help surfaces publish examples that are both:

- strict enough to verify; and
- stable enough to teach from one recognizable context.

## What a snippet world provides

A snippet world may provide a stable set of:

- inputs;
- runtime state values;
- read-only probe results;
- action outcomes;
- repeated domain entities such as repositories, issues, branches, project items, or task keys.

The point is not to simulate production reality in full detail.
The point is to provide one explicit and repeatable teaching environment for many snippets.

## Where snippet worlds are used

Snippet worlds are used in help and discovery publication, especially for:

- `ordo-help describe ...` canonical examples;
- canonical-example verification;
- snippet coverage reporting;
- future authoring-fragment examples that need shared surrounding context.

Snippet worlds may support examples for multiple forms, such as:

- expression values;
- step-field values;
- step fragments;
- workflow fragments.

## Where snippet worlds are not used

Snippet worlds must not be treated as:

- workflow runtime state semantics;
- user-authored workflow features;
- profile semantics;
- production execution environments;
- alternate sources of workflow truth.

They support help publication and verification only.

## Use conditions

Use a snippet world when an example:

- needs shared inputs, state, probe outputs, or action outcomes;
- should remain comparable to many other examples;
- is too small to stand alone as a complete workflow;
- should be shown as realistic authoring material without giving up strict verification.

Do not require a snippet world for examples that are already well served by:

- verified repository excerpts;
- self-contained complete examples;
- trivial isolated value validation.

## Relationship between world, snippet, and scaffold

The teaching model should keep three concerns separate:

- the snippet world supplies stable context;
- the snippet supplies authored example content;
- the scaffold or insertion mode supplies placement.

The world must not silently rewrite the snippet into a different authored form.
The snippet shown to the user should remain the snippet that is actually verified.

## Teaching goal

Snippet worlds exist so that many examples can belong to one stable teaching world rather than many ad hoc micro-contexts.

This should make examples:

- easier to recognize;
- easier to compare;
- easier to maintain;
- more useful as code to imitate.

## Stability rule

- A snippet world should be intentionally stable and boring.
- It should reuse the same entities and values across many examples unless a local variation is required.
- It must not become an opaque “everything passes here” environment.

## Verification rule

- Snippet-world verification may normalize only clearly safe authoring equivalences.
- It must not depend on semantic guessing.
- If the verifier cannot establish a safe equivalence, it must leave the example unmatched rather than inventing one.

## Multiplicity rule

- The help model may define more than one snippet world.
- Different worlds may exist for different teaching needs, connector families, or example shapes.
- No single snippet world should be assumed to be the only valid future teaching context.

## Adding a new world-backed snippet

When adding a new world-backed snippet, the author should make four decisions explicitly:

1. which snippet world supplies the teaching context;
2. which snippet form is being published;
3. which insertion mode or scaffold places the snippet into a verifiable host;
4. which verification mode proves the snippet stays valid.

The snippet world should answer only the first question.
It must not answer placement or rendering questions by itself.

### Contribution contract

- Choose an existing snippet world when it already supplies the needed teaching context.
- Add a new snippet world only when the example honestly needs a different stable teaching context rather than a local override.
- Declare the snippet form explicitly so readers can tell whether they are looking at a value example, a step-field example, a step fragment, or a workflow fragment.
- Declare the insertion mode explicitly so placement remains reviewable as a scaffold concern rather than leaking into world data.
- Keep the published snippet body aligned with the snippet that the verifier actually runs.
- Do not rely on decorative rendering tricks to make one snippet form look like another.
- Keep verification in repository tests rather than in normal `ordo-help` runtime calls.

### Verification expectations for contributors

- A new world-backed snippet should fail visibly when its verified shape drifts.
- A new world-backed snippet should participate in ordinary repository verification.
- If the supported snippet-world path cannot yet express the required example shape honestly, treat that as a support gap and call it out explicitly instead of inventing an unverifiable workaround.
