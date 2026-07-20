# Representation-adapter model

## Position

Representation adapters are modeled as one shared local-expression extension point with family-specific interior syntax and structure semantics.

The model therefore separates:

- the shared invocation and result discipline that lets adapter families participate consistently in local-expression evaluation;
- the family-specific path surface used inside one adapter family;
- the family-specific represented structure manipulated by that family.

## Shared modeled elements

### Adapter family

An adapter family is one product-defined representation-specific operation family such as `markdown`, `html`, `json`, or `string`.

It names the representation discipline through which one already available root value will be interpreted.

### Root value

An adapter root value is the already available value supplied to an adapter invocation.

The adapter does not own how that root value was obtained.
It only owns how that value is interpreted and transformed once supplied.

### Adapter invocation

An adapter invocation applies one adapter family to one root value through one adapter-defined path or action chain.

The shared modeled shape is:

- adapter family selection;
- root-value supply;
- adapter-defined interior navigation or selection;
- optional terminal mutation.

### Adapter-owned body

The model treats the interior body of an adapter invocation as adapter-owned.

That means:

- the shared seam identifies the adapter family and the extent of the adapter-owned body;
- the concrete adapter family owns parsing and interpretation of that interior body;
- the shared seam does not need one globally normalized grammar for family-specific search, navigation, or mutation syntax.

### Host-owned outer parameter binding

The model prefers host-owned parameter binding outside the adapter-owned body over host references embedded directly inside adapter-family grammar.

The model therefore separates:

- adapter-owned syntax and structure semantics inside the adapter body;
- host-owned value resolution for outer parameter bindings such as values derived from `inputs...`, `args...`, `state...`, `step...`, or read-only probes.

The intended modeled flow is:

- the shared seam identifies the adapter-owned body and any top-level trailing host binding suffix;
- canonical local-expression evaluation resolves the host-owned bindings under normal context policy;
- adapter evaluation receives the adapter-owned body plus resolved parameter values from the outer binding surface;
- adapter evaluation continues without taking ownership of host-root semantics.

The model prefers resolved parameter values from the outer binding surface over naive string substitution so host-owned values do not collapse prematurely into untyped text.

### Top-level trailing binding suffix

One workable modeled form is a top-level trailing host binding suffix such as ` with{...}` after the adapter-owned body.

In that form:

- the adapter-owned body remains family-specific;
- the trailing binding suffix remains host-owned;
- the shared seam only needs top-level lexical boundary detection rather than family-specific body parsing to separate the two.

### Cross-family value flow

The model permits ordinary composition across adapter families by value flow.

That means:

- one adapter invocation may yield a focus value or other derived value;
- that resulting value may become the root value of a later adapter invocation;
- the shared seam only needs to preserve value handoff, not family-specific knowledge of the next adapter's interior syntax.

This keeps cross-family composition as a normal consequence of value-producing adapter evaluation rather than as a special nested-adapter feature.

### Focus value

A focus value is the selected or derived value produced by a read invocation before any persistence semantics exist.

It may be:

- a scalar derived from the represented structure;
- a structured derived value;
- an addressable focus inside the represented structure suitable for further pure local evaluation.

### Terminal mutation

A terminal mutation is the final write operation in an adapter invocation.

It ends adapter navigation and produces an updated root value for the represented structure.

### Adapter outcome

An adapter outcome is the modeled result category returned by the shared adapter seam.

At minimum the model expects support for:

- successful selection or derivation;
- successful root update;
- `not_found`;
- `ambiguous`;
- `unsupported`;
- `invalid_path`;
- `invalid_action`;
- `invalid_root_value`.

The model also distinguishes host-side failures that occur while resolving the outer binding surface from adapter-side failures that occur after resolved parameter values have been supplied to the adapter family.

## Read-versus-write model

The model distinguishes two invocation kinds.

### Read invocation

A read invocation consumes a root value and yields a focus value or other derived value.

It does not create structure and does not update the root.

### Write invocation

A write invocation consumes a root value, applies one terminal mutation, and yields an updated root value.

It may auto-create missing structure only within the modeled write-path boundary.

## Auto-creation model

The modeled auto-creation rule is intentionally narrow:

- only write invocation may auto-create missing structure;
- each created step must be unambiguous;
- each created step must have a canonical family-defined shape;
- ambiguity blocks creation rather than being resolved implicitly.

## Boundary model

Representation adapters remain inside local-expression value derivation.

They are modeled as distinct from:

- connector execution;
- hidden I/O;
- persistence ownership;
- workflow control semantics.

## Modeling consequence

Because concrete families such as `markdown` require one shared invocation seam, the product model should not describe family-specific syntax without also modeling the shared adapter invocation boundary they rely on.
