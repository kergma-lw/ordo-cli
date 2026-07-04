# Runtime requirements for introspection

## Role

- The runtime must expose a machine-readable introspection surface for tools and agents.
- This surface exists so external consumers can discover supported contracts and capabilities without prose parsing or direct code-reading.

## Source of truth

- Published introspection must come from runtime-owned metadata or canonical contract data.
- Introspection must not be maintained as a separate descriptive mirror of implementation behavior.
- Human-facing prose may explain the surface but must not define it.

## Minimum surface

The runtime must be able to answer, in machine-readable form:

- what discovery entrypoint exists;
- what workflow and playbook contract surfaces are supported;
- what capability states are supported, unsupported, or planned;
- what expression roots, filters, builtins, and allowed surfaces are supported;
- what public operation metadata is available.

## Growth discipline

- New runtime-visible surface should be added through canonical metadata first or in the same change.
- The project should prefer one shared metadata source over separate runtime and help descriptions.
- Introspection should fail closed for covered surfaces rather than silently omitting changed behavior.
