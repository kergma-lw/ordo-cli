# JSON representation-adapter model

## Position

The `json` adapter family models one JSON-text representation surface over a string root value.

It keeps authored selection and action syntax family-specific while relying on the shared representation-adapter seam for outer ` with{...}` binding, read-versus-write distinction, and shared outcome categories.

## Core modeled targets

### Root text

The json root value is one whole string containing one complete JSON value.

### Parsed JSON value

The family parses the root text into one represented JSON value before json-family navigation begins.

That represented value may be an object, array, string, number, boolean, or `null`.

An invocation with an empty json-owned body models whole-root interpretation only and yields that complete parsed JSON value without further narrowing.

### Member focus

One object-member selection yields one singular member focus.

The family may expose that focus through dotted member access for simple keys or bracketed literal member access for keys that require explicit quoting.

### Element focus

One array-index selection yields one singular element focus.

Indexing is zero-based and models direct element addressing rather than search.

### Recursive-descent segment

The family may expose one recursive-descent segment written as `..`.

That segment does not introduce a second query language.
It means that the following structural path should be searched at any deeper depth below the current focus.

The intended model is intentionally narrow:

- `..` may appear at any one position in the path;
- only one `..` segment may appear in a single path;
- the path following `..` still consists of ordinary structural steps such as member access, bracketed literal keys, and array indexes.

The modeled result of recursive descent is many-valued.

## Read-result model

A successful read invocation yields the selected JSON-compatible value.

That value may itself be a structured object or array, or a scalar such as a string, number, boolean, or `null`.

The model therefore treats JSON `null` as one successful represented value rather than as adapter absence.

When a path contains recursive descent, the modeled read result is a collection of all matching values in traversal order.
If no recursive matches are found, the modeled read result is an empty collection rather than adapter absence.

## Write-action model

The MVP write surface is intentionally small.

The primary modeled actions are:

- `set(value)`;
- `remove()`.

Those actions operate over one selected JSON focus and return updated JSON text for the whole adapted root value.

`remove()` may also operate as one bulk action over a recursive-descent result set.

## Auto-creation model

The family inherits the shared write-only auto-creation boundary from the shared adapter model.

In the json family, the intended modeled form is narrow:

- missing object members may be created by write-path `set(value)` when each missing intermediate step is one unambiguous object-member step;
- each such created intermediate step has the canonical shape `{}`;
- missing array indexes do not auto-create synthetic elements or gaps.

## Failure model

The family may fail when:

- the root value is not a string containing valid JSON text;
- a selector step is incompatible with the current JSON node kind;
- a requested object member or array index does not exist;
- a terminal action is not valid for the selected node kind;
- an action argument cannot be represented in the product's ordinary JSON-compatible value model.

The family does not model missing recursive-descent matches as `not_found` for read or bulk-remove behavior.

The shared adapter seam should continue to distinguish adapter-family failures from host-side failures that occur while resolving outer binding values.

## Serialization model

The family serializes any successful write result back to JSON text.

The model does not require preservation of original whitespace, indentation, or other source-format trivia.
It only requires that the returned root text be valid JSON and deterministic for the same updated represented value under the same product version.

## Boundary model

The family remains a representation adapter over JSON text rather than a general-purpose query language over arbitrary structured runtime values.

It is modeled as distinct from:

- ordinary local-expression navigation over already structured values;
- JSONPath-style filter or predicate semantics;
- persistence ownership for the updated JSON text;
- connector execution or hidden I/O.
