# Text representation-adapter requirements

## Role

- The `text` representation adapter is a product-defined local-expression surface for interpreting and transforming already available plain-text string values.
- This document defines text-family behavior within the shared representation-adapter invocation seam described in `requirements/local-expressions/adapters.md`.
- The text family should remain narrow and predictable rather than becoming a general grep, regex, or stream-editing language.

## Compatibility target

- The adapter should target stable plain-text semantics over ordinary newline-delimited strings.
- The adapter should not claim richer document structure such as markdown sections or universal paragraphs.
- The adapter should prefer literal authored behavior over heuristic tokenization, linguistic inference, or dialect-specific parsing.

## Authored path surface

- Text path syntax belongs to the text adapter contract rather than to the shared local-expression core.
- The shared adapter seam should identify the text family and the extent of the text-owned body, while text-family parsing owns the interior text-specific selector and action syntax.
- Optional host-derived parameterization should live outside the text-owned body through the shared adapter binding surface rather than through host references embedded directly inside text-family grammar.
- The family should expose `.lines` for line-oriented projection.
- The family should expose `.find("...")` for singular literal substring selection.
- The family should expose `.finds("...")` for plural literal substring selection.
- The family should expose `before("...")` and `after("...")` as singular anchor-based narrowing selectors.
- Positional disambiguation uses `[n]`.

## Search and anchor semantics

- `find`, `finds`, `before`, and `after` should use literal substring matching only.
- The family should not infer token, word-boundary, case-insensitive, or regex semantics unless such behavior is introduced later as separate explicit surface.
- A literal authored to `before("...")` or `after("...")` therefore matches ordinary substring occurrences even when they appear inside larger words.
- `find("...")` must require exactly one match.
- `before("...")` and `after("...")` must require exactly one anchor occurrence within the current singular text scope.
- `.finds("...")` should return matches in source order.
- `.finds("...")` should model non-overlapping matches.

## Collection surface

- `.lines` should return an ordered collection of line focuses.
- `.finds("...")` should return an ordered collection of match focuses.
- `.lines` applied to the empty string must return an empty collection.
- `[n]` applied to a collection should select one singular member by zero-based index.
- `[n]` with an out-of-range index must fail as `not_found`.

## Singular-versus-collection boundary

- Singular text scopes may support further text selectors such as `.lines`, `.find`, `.finds`, `before`, and `after`, plus terminal text actions.
- A selected line focus is a singular text scope.
- A singular match focus is a singular text scope.
- Collection-valued focuses should not support further narrowing or search selectors directly.
- Collection-valued focuses may support terminal bulk mutation when that mutation can be applied independently across ordered non-overlapping members.

## Selection semantics

- The shared read-versus-write boundary and shared adapter outcome vocabulary come from `requirements/local-expressions/adapters.md`.
- Read paths must never create structure.
- `find("...")`, `before("...")`, and `after("...")` must fail as `not_found` when no match exists in the current singular text scope.
- `find("...")`, `before("...")`, and `after("...")` must fail as `ambiguous` when more than one match exists in the current singular text scope.
- `.finds("...")` should return an empty collection rather than fail when no matches exist.
- The adapter must not silently apply implicit first-match or last-match selection.

## Terminal action surface

- A trailing `->action(...)` form may denote a terminal mutation over the selected text focus or over one eligible collection focus.
- A terminal text mutation is one text-family instance of the shared adapter write-invocation rule that returns the updated root value.
- Action names should remain author-comprehensible rather than exposing parser internals.
- The text family should expose a small orthogonal text-action surface consisting of `append(text)`, `replace(text)`, and `remove()`.
- Text action arguments should be plain text rather than structured payloads.
- `remove()` should be equivalent in effect to replacing the selected focus with the empty string.

## Bulk mutation discipline

- Bulk mutation over a collection focus is allowed only when the targeted members are ordered and non-overlapping.
- Bulk mutation over a line collection should apply independently to each selected line focus in source order.
- Bulk mutation over a match collection should apply independently to each selected match focus in source order.
- Bulk mutation over an empty collection should succeed as a no-op and return the unchanged root value.
- The family must not imply hidden map, filter, flatten, or regroup semantics for non-terminal collection selectors.

## Product-shape guidance

- The family should remain a narrow plain-text adapter rather than a full document-structure adapter.
- The family should prefer stable literal scope narrowing and explicit collection handling over heuristic or implicit semantics.
- If richer text structure or richer search modes are needed later, they should be introduced as explicit new surface rather than silently overloaded into the MVP text contract.
