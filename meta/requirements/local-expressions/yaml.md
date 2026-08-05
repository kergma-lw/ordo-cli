# YAML representation-adapter requirements

## Role

- The `yaml` representation adapter is a product-defined local-expression surface for interpreting already available YAML text.
- This document defines yaml-family behavior within the shared representation-adapter invocation seam described in `requirements/local-expressions/adapters.md`.
- The family should remain a YAML-text adapter for one document rather than a generic structured-value navigation surface.

## Compatibility target

- The adapter should target one YAML document whose parsed content is representable as canonical JSON-shaped data.
- The adapter should accept YAML mappings, sequences, strings, numbers, booleans, and null values that normalize cleanly into the product's JSON-shaped value model.
- The MVP should not promise authored-surface preservation for comments, quoting style, block-scalar style, anchors, aliases, or merge-key syntax.
- The MVP should reject multi-document YAML rather than introducing document-stream navigation.

## Root and result contract

- The root value must be a plain-text string containing exactly one YAML document.
- A read path must parse that root text as YAML before yaml-family navigation begins.
- An empty yaml adapter body is valid and must return the complete parsed YAML root value.
- A successful read path may return any YAML-derived JSON-shaped value, including an object, array, scalar, or `null`.
- A root string that is not valid single-document YAML, or whose parsed value is not representable as canonical JSON-shaped data, must fail as `invalid_root_value`.

## Authored path surface

- YAML path syntax belongs to the yaml adapter contract rather than to the shared local-expression core.
- The shared adapter seam should identify the yaml family and the extent of the yaml-owned body, while yaml-family parsing owns the interior yaml-specific selector syntax.
- Optional host-derived parameterization should live outside the yaml-owned body through the shared adapter binding surface rather than through host references embedded directly inside yaml-family grammar.
- The family should permit the adapter-owned body to be empty for whole-root parse-and-return behavior.
- The MVP path surface should support exact structural selection plus one explicit level-local filter segment for selecting children on the current focus.
- The family should support dotted member access such as `.name` for simple literal mapping keys.
- The family should support bracketed literal member access such as `["display-name"]` when a key cannot be expressed through the simple dotted form.
- The family should support zero-based array indexing such as `[0]`.
- The family should support `.one(field=value)` and `.one(field!=value)` to select one immediate child candidate by simple field comparison.
- The family should support `.many(field=value)` and `.many(field!=value)` to collect all immediate child candidates by simple field comparison.
- The MVP should not introduce recursive descent, wildcard selection, or search-like selectors.

## Selection semantics

- The shared read-versus-write boundary and shared adapter outcome vocabulary come from `requirements/local-expressions/adapters.md`.
- Read paths must never create structure.
- `.one(...)` and `.many(...)` must examine only immediate child candidates of the current focus.
- For a sequence focus, those child candidates are the sequence elements in sequence order.
- For a mapping focus, those child candidates are the mapping values in mapping-member traversal order.
- For a scalar focus, `.one(...)` and `.many(...)` must fail as `invalid_path`.
- Only child candidates that are themselves objects and contain the requested field participate in `=` or `!=` matching.
- A missing mapping member must fail as `not_found`.
- A missing sequence index must fail as `not_found`.
- A YAML null value is a successful found value rather than `not_found`.
- A path step that is not valid for the current YAML node kind, such as member selection on a sequence or array indexing on a scalar, must fail as `invalid_path`.
- The adapter must not apply implicit scalar-to-object, scalar-to-array, or string-to-number coercion during path evaluation.
- `.one(...)` with zero matches must fail as `not_found`.
- `.one(...)` with more than one match must fail as `ambiguous_match`.
- `.many(...)` must return one array of matching child values, with `[]` for zero matches.
- `.many(...)` may be followed by ordinary array indexing such as `[0]`, after which ordinary navigation rules resume.

## Write boundary

- The yaml adapter inherits the shared write-path boundary from `requirements/local-expressions/adapters.md`.
- The MVP should be read-only.
- Any terminal mutation surface such as `->...` must fail as `invalid_action`.

## Product-shape guidance

- The yaml family should stay intentionally close to the `json` adapter for basic structural navigation so users can carry the same mental model across both text representations.
- The MVP should expose parsed data values rather than authored YAML formatting trivia.
- If later product needs require multi-document support, anchor-aware navigation, or style-preserving writes, those concerns should be introduced explicitly as later yaml-family surface rather than implied by the MVP.
