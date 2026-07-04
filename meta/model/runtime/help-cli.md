# Help CLI discovery model

## Root contract

The root `ordo-help` surface should answer four questions in order:

1. what the tool is;
2. what it can describe;
3. how to ask for that information;
4. what the recommended next queries are.

The text root may be concise, but it should still publish:

- tool name;
- one-line purpose;
- output modes;
- top-level topics;
- recommended next commands.

The JSON root should carry the same semantic content in machine-readable form.

## Public commands

The initial public command model is:

```bash
./ordo-help [--json]
./ordo-help overview [--json]
./ordo-help capabilities [--json]
./ordo-help model [--json]
./ordo-help operations [--json]
./ordo-help examples [--json]
./ordo-help operation <reference> [--json]
./ordo-help describe <topic> [--json]
./ordo-help search <query> [--json]
```

The public contract should remain topic-oriented rather than exposing implementation module names directly.

## Topic mapping

- `overview` aggregates the world map needed before authoring or execution planning.
- `capabilities` exposes supported, unsupported, and planned surface states.
- `model` aggregates the main authoring contracts over workflows, profiles, playbooks, and runtime state.
- `operations` exposes the public connector operation catalog.
- `examples` exposes verified repository examples intended as public authoring references.
- `operation <reference>` exposes one focused operation contract.
- `describe <topic>` resolves a supported public topic, capability node, or model node to the same canonical discovery surface.
- `search <query>` helps a caller bridge from vague terms to public topics, published contract facts, or operation references.

## Bootstrap sequence

The initial recommended bootstrap sequence is:

```bash
./ordo-help --json
./ordo-help overview --json
./ordo-help capabilities --json
./ordo-help model --json
./ordo-help operations --json
./ordo-help examples --json
```

This sequence should let a zero-knowledge caller discover:

- the purpose and scope of Ordo;
- the main supported and unsupported capability boundaries;
- the main authoring surfaces and contracts;
- the public executable operation inventory.

## Boundary rule

`ordo-help` should translate runtime-owned introspection into a caller-friendly public vocabulary, but it should not become an alternate semantic source of truth.
