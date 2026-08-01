# JSON representation-adapter requirements

## Role

- The `json` representation adapter is a product-defined local-expression surface for interpreting and transforming already available JSON text.
- This document defines json-family behavior within the shared representation-adapter invocation seam described in `requirements/local-expressions/adapters.md`.
- The family should remain a JSON-text adapter rather than a generic structured-value navigation surface.

## Compatibility target

- The adapter should target strict JSON text semantics over one complete JSON value.
- The adapter should accept ordinary JSON objects, arrays, strings, numbers, booleans, and `null`.
- The adapter should not accept comments, trailing commas, unquoted keys, or other JSON5- or JSONC-style extensions in the MVP.

## Root and result contract

- The root value must be a plain-text string containing one complete JSON value.
- A read path must parse that root text as JSON before json-family navigation begins.
- An empty json adapter body is valid and must return the complete parsed JSON root value.
- A successful read path may return any JSON-compatible derived value, including an object, array, scalar, or `null`.
- A write path must return updated JSON text rather than a structured in-memory root value.
- A root string that is not valid JSON must fail as `invalid_root_value`.

## Authored path surface

- JSON path syntax belongs to the json adapter contract rather than to the shared local-expression core.
- The shared adapter seam should identify the json family and the extent of the json-owned body, while json-family parsing owns the interior json-specific selector and action syntax.
- Optional host-derived parameterization should live outside the json-owned body through the shared adapter binding surface rather than through host references embedded directly inside json-family grammar.
- The MVP path surface should support exact structural selection plus one recursive-descent selector.
- The family should permit the adapter-owned body to be empty for whole-root parse-and-return behavior.
- The family should support dotted member access such as `.name` for simple literal object keys.
- The family should support bracketed literal member access such as `["display-name"]` when a key cannot be expressed through the simple dotted form.
- The family should support zero-based array indexing such as `[0]`.
- The family should support one recursive-descent selector written as `..`.
- `..` may appear at any one position in a path.
- A path must not contain more than one `..` segment.
- `..` should apply only to later structural path steps rather than introducing a predicate or query sublanguage.
- The MVP should not introduce filters, wildcard selection, or JSONPath-style predicate semantics.

## Selection semantics

- The shared read-versus-write boundary and shared adapter outcome vocabulary come from `requirements/local-expressions/adapters.md`.
- Read paths must never create structure.
- A missing object member must fail as `not_found`.
- A missing array index must fail as `not_found`.
- A JSON `null` value is a successful found value rather than `not_found`.
- A path step that is not valid for the current JSON node kind, such as member selection on an array or array indexing on a scalar, must fail as `invalid_path`.
- The adapter must not apply implicit scalar-to-object, scalar-to-array, or string-to-number coercion during path evaluation.
- A recursive-descent segment must search for the following structural path at any deeper depth below the current focus.
- A recursive-descent read path is many-valued.
- A recursive-descent read path with no matches should return an empty collection rather than `not_found`.

## Terminal action surface

- A trailing `->action(...)` form may denote a terminal mutation over the selected JSON focus.
- A terminal json mutation is one json-family instance of the shared adapter write-invocation rule that returns updated JSON text.
- The MVP action surface should remain small and explicit.
- The MVP should support `set(value)` to replace the selected value or create one eligible missing target under the write-path auto-creation rules below.
- The MVP should support `remove()` to delete the selected object member or array element.
- JSON action arguments should be resolved ordinary Ordo values that can be represented as JSON without adapter-specific hidden coercion.
- If an action argument cannot be represented as JSON under the product's ordinary JSON-compatible value model, the action must fail rather than silently stringifying or dropping information.
- A bulk `remove()` over a recursive-descent result is valid.
- A bulk `remove()` over a recursive-descent result with no matches should succeed as a no-op and return the unchanged root text.

## Write-path auto-creation

- The json adapter inherits the shared write-only auto-creation boundary from `requirements/local-expressions/adapters.md`.
- Read paths must not auto-create structure.
- `set(value)` may auto-create missing object members only when each missing intermediate step is an unambiguous object-member step with a canonical created shape of `{}`.
- Write-path auto-creation must not invent array elements merely to bridge a missing index.
- Write-path auto-creation must not create through ambiguity, search-like selection, or invalid path steps.
- `remove()` must not auto-create anything.

## Array mutation boundary

- `remove()` applied to an array target should remove exactly one selected element and re-close the array in ordinary JSON array order.
- `set(value)` targeting one existing array element should replace that element in place.
- `set(value)` targeting a missing array index must fail as `not_found` rather than creating index gaps.

## Serialization discipline

- A successful write path must return valid JSON text representing the updated root value.
- The write result may normalize formatting rather than preserving the original whitespace, indentation, or line wrapping of the input text.
- The adapter should produce deterministic serialization for the same updated JSON value under the same product version.
- The MVP does not need to preserve source trivia or formatting style as part of the adapter contract.

## Product-shape guidance

- The family should remain a representation adapter over JSON text, not a second general-purpose object query language.
- The MVP should prefer simple structural paths plus one explicit recursive-descent surface over generic filter or predicate syntax.
- If later product needs require richer selectors such as filters or wildcard queries, they should be introduced explicitly as later json-family surface rather than implied by the MVP.
