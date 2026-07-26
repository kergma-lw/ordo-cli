# Markdown representation-adapter model

## Position

The `markdown` adapter family models one text-oriented representation surface over a markdown root string.

It keeps authored selection and action syntax family-specific while relying on the shared representation-adapter seam for outer ` with{...}` binding, read-versus-write distinction, and shared outcome categories.

## Core modeled targets

### Document

The markdown root value is one whole markdown document string.

### Prelude

The markdown prelude is the portion of the document that appears before the first heading.

Prelude is modeled as always present.
If the document starts with a heading, prelude still exists as the empty leading markdown slice rather than as `not_found`.

### Section

A markdown section is one heading plus the markdown text governed by that heading.

Selecting a section does not require the adapter family to collapse the selection immediately to only the section body.
Further selector steps or terminal action semantics may refine how the selected section text is used.

### Block-oriented targets

The family may expose block-oriented targets such as paragraphs and lists inside a section or prelude scope.

After one singular list or task-list block has been selected, the model may allow positional indexing to address one top-level list item within that selected block.

The family may also expose a separate collection-view projection for list-like blocks, for example `.list_items` or `.task_list_items`, when the product wants an array-valued view distinct from the richer block object.

## Text-action model

The markdown family should prefer a small orthogonal text-action surface over many special-case action verbs.

The primary modeled actions are:

- `append(text, prefix="")`;
- `replace(text)`;
- `remove()`.

Those actions consume plain text arguments rather than structured object payloads.

The adapter family may interpret the selected markdown target to decide where the resulting text is inserted or replaced, but it does not need a public object-shaped fragment argument model.

## List mutation model

Because nested lists make generic append semantics ambiguous at the list level, list targets may expose one list-specific action such as `add(text)`.

`add(text)` models adding one new list item at the current list level rather than performing a generic text splice into an arbitrary list location.

## Argument discipline

Markdown action arguments are modeled as plain text.

The family should not require object-valued public action payloads merely to support large or structurally rich markdown text.

The family may still use its own internal parsing or normalization as an implementation detail when editing the root markdown string, but that does not change the modeled public action argument shape.
