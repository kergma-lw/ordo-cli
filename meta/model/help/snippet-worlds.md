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
