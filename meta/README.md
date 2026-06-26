# Ordo meta

Internal contract documentation for the project.

Purpose of `meta/`:
- keep the source of truth ahead of and above code;
- record requirements, domain model, and format data;
- reduce drift between `schema/`, `docs/`, runtime, and examples;
- provide a stable reference for both humans and agents.

Workflow source may be authored in YAML, but canonical runtime-facing structures and runtime results are JSON-shaped and losslessly JSON-serializable.

## Map

- `requirements/` — requirements organized by domain
- `domain/` — domain descriptions for connector/workflow/runtime/policy
- `model/` — entities and relationships organized by domain
- `data/` — data shapes and envelopes organized by domain
- `scenarios/` — canonical use cases
- `adr/` — architecture decisions
- `verification/` — checks and invariants organized by domain
- `notes/` — longer positioning and project notes
- `domain-packs.toml` — derived pack assembly config
- `packs/` — generated artifacts built from the source documents above

Source documents in `meta/` are organized first by document type,
and then by domain, for example:
- `requirements/connector/**`
- `model/runtime/**`
- `data/workflow/**`
- `verification/meta/**`

## Rule

If code, schema, examples, or README drift from `meta/`, update `meta/` first and then bring everything else back into sync.

`meta/packs/**` is a generated layer and must not be edited by hand.

Regenerate packs with `python3 tools/build_domain_packs.py meta/domain-packs.toml`.
Verify generated packs with `python3 tools/build_domain_packs.py meta/domain-packs.toml --check`.

## Contract hotspots

For a compact entry point into the core contract, start with:
- `model/connector/contract.md`
- `model/connector/resolution-policy.md`
- `verification/runtime/invariants.md`
