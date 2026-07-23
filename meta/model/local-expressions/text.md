# Text representation-adapter model

## Position

The `text` adapter family models one plain-text representation surface over a string root value.

It keeps authored selection and action syntax family-specific while relying on the shared representation-adapter seam for outer ` with{...}` binding, read-versus-write distinction, and shared outcome categories.

## Core modeled targets

### Root text

The text root value is one whole plain-text string.

### Text scope

A text scope is one singular text slice that may serve as the current surface for further narrowing, searching, projection, or terminal mutation.

The root text is a text scope.
Derived singular text slices such as the result of `before("...")`, `after("...")`, or a singular substring match are also text scopes.

### Line collection

The family may project one text scope into an ordered collection of line focuses through `.lines`.

The line collection is modeled as a collection view rather than as a second root.
It exists so authored expressions can inspect or mutate line-oriented targets without claiming richer document semantics such as paragraphs or sections.

### Line focus

One indexed line selected from a line collection is a singular text scope.

That means a selected line may participate in further singular text operations such as search, narrowing, or terminal mutation.

### Match collection

The family may project one text scope into an ordered collection of literal substring matches through `.finds("...")`.

The match collection models zero or more non-overlapping matches in source order.

### Match focus

The family may expose one singular substring match either directly through `.find("...")` or by indexing into a match collection.

A singular match focus is a text scope.
That means search narrowing may continue after one singular match has been selected.

## Anchor narrowing model

The family may expose singular anchor-narrowing selectors such as `before("...")` and `after("...")`.

Those selectors consume one singular text scope and yield one further singular text scope bounded around one unique literal anchor occurrence.

## Collection boundary model

Collections remain ordered views over multiple focuses.

The model permits:

- indexing into a collection to recover one singular focus;
- terminal bulk mutation over a collection when the targeted members are ordered and non-overlapping.

The model does not require collection-valued focuses to support further narrowing or search selectors directly.

## Search model

The text family models literal substring search rather than token-aware search, regex search, or rich linguistic structure.

That means authored literals match ordinary substring occurrences even when they appear inside larger words or tokens.

## Text-action model

The family may expose a small text-action surface over singular focuses and selected collection views.

The primary modeled actions are:

- `append(text)`;
- `replace(text)`;
- `remove()`.

Those actions consume plain text arguments rather than structured payloads.

## Empty-line projection model

Projecting `.lines` from the empty string yields an empty collection.

The family therefore treats empty text as having zero projected line focuses rather than one synthetic empty line focus.
