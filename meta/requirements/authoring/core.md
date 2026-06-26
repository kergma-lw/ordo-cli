# Authoring requirements

## Product quality

- Agent-authorable workflow and profile composition is a core product quality, not a secondary convenience.
- The system must allow a sufficiently capable agent to learn how to compose workflows and profiles from the documented contract surface.
- Authoring support must focus first on workflows, profiles, and related declarative configuration built from existing public operations.
- Fast authoring of new connector families or operations is not a required early-stage customization path.

## Discoverability

- An author must be able to discover which public operations exist and what contracts they expose.
- An author must be able to infer the stable shape of workflows and profiles from schema, examples, and contract documentation.
- The system should prefer composition over invention: composing existing operations and profiles is the default extension path.

## Checkability

- An authored workflow or profile must be machine-checkable before execution.
- The system must help an agent distinguish at least validity, resolution, likely executability, and authoring-quality concerns.
- Validation and explanation surfaces must be structured enough for an agent to iteratively repair an authored workflow without guessing from logs.
