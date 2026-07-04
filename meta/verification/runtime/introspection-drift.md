# Verification for introspection drift

## Rule

If a runtime-visible surface changes, the published introspection surface must change in the same work.

## Runtime-visible surface

At minimum this includes:

- root discovery surface;
- workflow contract surface;
- playbook contract surface;
- capability states exposed to tools;
- expression roots, filters, builtins, and allowed surfaces;
- public operation metadata exposed for machine-readable consumption.

## Source-of-truth rule

Introspection must be assembled from runtime-owned metadata or from canonical contract data owned by the runtime-facing product layer.

Prose documents must not be the source of truth for published introspection.

## Enforcement expectations

The project must verify, at minimum:

- published introspection is machine-readable;
- published introspection is versioned;
- covered runtime-visible surface changes fail verification when introspection is not updated;
- parity checks detect drift between runtime-owned metadata and published introspection output.

## Review rule

A change that widens, narrows, renames, removes, or reclassifies a covered runtime-visible surface is incomplete unless the corresponding introspection and verification updates are included in the same work.
