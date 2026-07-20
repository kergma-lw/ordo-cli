# Markdown representation-adapter requirements

## Role

- The `markdown` representation adapter is a product-defined local-expression surface for interpreting and transforming already available markdown text.
- This document defines markdown-family behavior within the shared representation-adapter invocation seam described in `requirements/local-expressions/adapters.md`.
- It should prioritize compatibility with typical GitHub-authored markdown text without introducing a separate `github_markdown` adapter family.

## Compatibility target

- The adapter should target a stable markdown document model suitable for general markdown inputs.
- Compatibility should prioritize common CommonMark and commonly used GitHub Flavored Markdown constructs.
- The adapter contract should document supported constructs and should not promise perfect reproduction of every source-specific markdown dialect detail.

## Authored path surface

- Markdown path syntax belongs to the markdown adapter contract rather than to the shared local-expression core.
- The shared adapter seam should identify the markdown family and the extent of the markdown-owned body, while markdown-family parsing owns the interior markdown-specific selector and action syntax.
- Optional host-derived parameterization should live outside the markdown-owned body through the shared adapter binding surface rather than through host references embedded directly in markdown-family grammar.
- Literal title selection uses `["..."]` in authored examples, where the string is treated as a literal title or literal named selector value.
- The adapter should expose an always-present `prelude` selector for the markdown text that appears before the first heading.
- Positional disambiguation uses `[n]`.
- Explicit structural selection may use adapter-defined forms such as `.blocks("kind")`.
- The adapter may provide common structural shortcuts such as `.list`, `.task_list`, or `.paragraph` as convenience sugar over the explicit structural form.
- The adapter may provide text-search helpers such as `.find("...")` when the product needs them.

## Outer parameter binding

- When markdown-family behavior needs host-derived values, those values should be supplied through the shared outer adapter binding surface rather than embedded directly inside markdown-family syntax.
- Markdown-family evaluation should therefore consume resolved parameter values rather than unresolved host-owned references.
- Host-derived parameter values may parameterize markdown-family selectors or action arguments, but they should not be treated as a way to generate markdown-family grammar dynamically.
- One preferred form is a trailing host-owned binding suffix such as ` with{...}` after the markdown-owned body.

## Shortcut discipline

- Any shortcut must remain convenience sugar over one explicit markdown-adapter form.
- A shortcut must not introduce semantic behavior that is unavailable in the explicit form.
- A shortcut must not weaken normal `not_found`, `ambiguous`, or write-path auto-creation rules.
- A shortcut should expand to one stable explicit interpretation rather than depending on hidden heuristics.
- If the adapter offers both singular and plural structural shortcuts, their plurality semantics should remain consistent across node kinds.
- If the adapter offers paired singular and plural structural shortcuts, the singular form should denote an expect-one convenience form and the plural form should denote the corresponding many-valued explicit selection.

## Selection semantics

- The shared read-versus-write boundary and shared adapter outcome vocabulary come from `requirements/local-expressions/adapters.md`.
- Read paths must never create structure.
- A path that yields zero matches must fail as `not_found`.
- A path that yields multiple matches without explicit disambiguation must fail as `ambiguous`.
- The adapter must not silently apply implicit first-match selection.

## Terminal action surface

- A trailing `->action(...)` form may denote a terminal mutation over the selected markdown focus.
- A terminal markdown mutation is one markdown-family instance of the shared adapter write-invocation rule that returns the updated root value.
- Action names should remain author-comprehensible rather than exposing low-level parser internals.
- The markdown family should prefer one small orthogonal text-action surface for markdown text targets, such as `append(text, prefix="")`, `replace(text)`, and `remove()`.
- `append` should accept one plain text argument plus an optional plain text prefix argument whose default is the empty string.
- Markdown action arguments should be plain text rather than structured object payloads.
- The family may still expose one list-specific action such as `add(text)` when nested-list structure makes generic append semantics ambiguous at the list level.
- Large, multi-paragraph, or otherwise structurally rich markdown action text should still be treated as plain text input rather than forcing a different public payload shape.

## Prelude semantics

- `prelude` is always present.
- If a document begins with a heading, `prelude` still exists as the empty leading markdown slice rather than failing as `not_found`.
- Read and write markdown semantics should therefore treat prelude as one stable target rather than as an optional convenience surface.

## Write-path auto-creation

- The markdown adapter inherits the shared write-only auto-creation boundary from `requirements/local-expressions/adapters.md`.
- Write paths may auto-create missing structure only when each missing step is unambiguous and has a canonical markdown shape.
- Auto-creation must never pass through ambiguity.
- Search-based selectors must not trigger implicit creation.
- Read paths must not auto-create structure.

## Product-shape guidance

- The explicit form defines canonical markdown-family semantics within the shared adapter seam.
- Any shorter GitHub-friendly forms should remain convenience syntax layered over the explicit form rather than separate semantics.
