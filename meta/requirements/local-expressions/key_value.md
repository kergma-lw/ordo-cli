# Key-value representation-adapter requirements

## Role

- The `key_value` representation adapter is a product-defined local-expression surface for interpreting an already available plain-text root as a flat set of line-oriented key/value records.
- This document defines key-value-family behavior within the shared representation-adapter invocation seam described in `requirements/local-expressions/adapters.md`.
- The family should remain a small read-only value-interpretation surface rather than growing into a generic config parser.

## Compatibility target

- The adapter should target stable plain-text semantics over newline-delimited records.
- The adapter should model one flat string-to-string mapping only.
- The adapter should not claim richer structure such as nesting, sections, arrays, or typed scalar inference.

## Root and parameter contract

- The root value must be a plain-text string.
- The family requires one `separator` parameter supplied through the shared outer binding surface.
- `separator` must be a non-empty literal string.
- The family should not infer or auto-detect separators from the root text.

## Record model

- The root text is interpreted as zero or more logical records separated by ordinary newline boundaries.
- Empty lines should be ignored.
- Leading and trailing whitespace on each non-empty line should be ignored before record parsing.
- Each remaining non-empty line must contain the configured separator.
- A record must split on the first separator occurrence only.
- The text before that first separator is the raw key text.
- The text after that first separator is the raw value text.

## Key and value normalization

- Key text should be trimmed.
- Value text should be trimmed.
- Empty keys are invalid.
- Empty values are allowed.
- If the trimmed value is wrapped in one matching outer single-quote pair or one matching outer double-quote pair, the adapter should remove exactly one such outer pair.
- The family should not apply escape processing inside quoted values.
- Unmatched quote characters should be treated as ordinary value text.

## Duplicate handling

- Duplicate keys are an error.
- The family must not silently apply first-write-wins or last-write-wins duplicate resolution.

## Read surface

- The MVP read surface should return the full flat object mapping string keys to string values.
- The family does not need an adapter-owned key-lookup subgrammar in the MVP if downstream object access can read the returned mapping.

## Explicit non-goals

- The family should not implement write paths in the MVP.
- The family should not model dotenv-specific, YAML-specific, TOML-specific, INI-specific, or shell-specific semantics beyond the shared flat delimiter-based contract above.
- The family should not support nesting, multiline values, escaping languages, section headers, include/import behavior, or typed value coercion.
- The family should not become a format auto-detection surface for arbitrary config files.

## Product-shape guidance

- The family should stay small enough that one user can understand the whole surface from the published help metadata and one short requirements document.
- If later product needs require richer config semantics, they should be introduced as explicit new adapter families rather than silently overloaded into `key_value`.

## Example shape

- Given a plain-text root such as:

  ```text
  host: "db.internal"
  port: 5432
  mode : readonly
  ```

  and `separator: ":"`, the adapter should produce a flat object equivalent to:

  ```json
  {"host": "db.internal", "port": "5432", "mode": "readonly"}
  ```
