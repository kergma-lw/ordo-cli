# Key-value representation-adapter model

## Position

The `key_value` adapter family models one flat line-oriented key/value representation over a string root value.

It relies on the shared representation-adapter seam for outer ` with{...}` binding, read invocation dispatch, and shared adapter outcome categories while keeping key-value parsing rules family-specific.

## Core modeled targets

### Root text

The root value is one whole plain-text string.

### Separator parameter

The family receives one required `separator` parameter from the host-owned outer binding surface.

That parameter chooses the literal delimiter used to split each record into key text and value text.

### Record line

One non-empty logical line from the root text is one candidate key/value record.

The family trims the line, then interprets the first separator occurrence as the boundary between raw key text and raw value text.

### Flat entry

One successfully parsed record contributes one flat string key and one flat string value to the represented mapping.

The family does not model nested paths, sections, or typed scalar nodes.

### Flat mapping result

A successful MVP read invocation yields one flat object mapping string keys to string values.

That object is the modeled read result rather than an addressable adapter-owned focus hierarchy.

## Normalization model

The family trims outer whitespace around keys and values.

It may normalize one value further by removing exactly one matching outer single-quote pair or outer double-quote pair.

The family does not model escaping or typed coercion inside the resulting value text.

## Failure model

The family may fail read evaluation when:

- the root value is not a string;
- `separator` is missing or invalid;
- a non-empty record line does not contain the separator;
- a parsed key is empty;
- the represented mapping would contain duplicate keys.

Those are adapter-family failures that occur after host-owned outer binding values have been resolved and supplied.

## Boundary model

The family remains a pure local-expression interpretation surface.

It is modeled as distinct from:

- connector-based file observation;
- generic config-format detection;
- persistence or file mutation ownership;
- richer structured configuration models such as YAML, JSON, or TOML.
