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

## Public topic commands

The initial public command model is:

```bash
./ordo-help [--json]
./ordo-help overview [--json]
./ordo-help capabilities [--json]
./ordo-help model [--json]
./ordo-help command-line [--json]
./ordo-help operations [--json]
./ordo-help examples [--json]
./ordo-help operation <reference> [--json]
./ordo-help describe <topic> [--json]
./ordo-help search <query> [--json]
```

The public contract should remain topic-oriented rather than exposing implementation module names directly.

## Discovery action commands

- `operation <reference>` resolves one focused operation contract.
- `describe <topic>` resolves one supported public topic or subtopic to the same canonical discovery surface.
- `search <query>` helps a caller bridge from vague terms to public topics, contract facts, or operation references.

These actions are navigation surfaces over the public topic model rather than additional top-level topics.

## Topic mapping

- `overview` aggregates the world map needed before authoring or execution planning.
- `capabilities` exposes supported, unsupported, and planned surface states.
- `model` aggregates the main authoring contracts over workflows, profiles, playbooks, and runtime state.
- `command-line` exposes the public launch-command surface, stable flag semantics, and the distinct roles of `ordo-playbook check` and `ordo-playbook review`.
- `operations` exposes the public connector operation catalog.
- `examples` exposes verified repository examples intended as public authoring references.
- `operation <reference>` exposes one focused operation contract.
- `describe <topic>` resolves a supported public topic, capability node, or model node to the same canonical discovery surface.
- `search <query>` helps a caller bridge from vague terms to public topics, published contract facts, or operation references.

## Workflow authoring pass pair

When a caller is adding or changing a workflow, `ordo-help` should make the authoring loop explicit:

- `ordo-playbook check <workflow>` answers whether the workflow is applicable and execution-ready now.
- `ordo-playbook review <workflow>` answers whether the workflow has authoring-quality findings.
- `check` and `review` are complementary authoring passes; neither replaces the other.

The public help surface should present this pairing in at least the `overview`, `workflow-authoring`, and `command-line` topics so a zero-knowledge caller does not infer that `check` alone is sufficient workflow sign-off.

## Publish payload discipline

`ordo-help workflow-authoring` should also warn against overstuffed `publish` payloads.

- Treat extra published fields as an authoring smell, not as harmless bonus detail.
- Publish only the minimum outward-facing payload needed by the caller or by one downstream workflow that must make a decision from it.
- If one field already identifies the result well enough, do not also publish redundant confirmation fields beside it.
- Do not mirror large action outputs into `publish` by default just because they are available.
- Do not publish `repository`, `issue_number`, `changed`, `closed`, or similar step-level confirmation fields when `url` or `issue_ref` already identifies the result sufficiently.
- If one field is not needed by a downstream workflow or by the user to make a decision, do not publish it.
- Respect stricter local agent or project rules when they ask for an even smaller success surface.

`ordo-help workflow-authoring` should show one short contrastive example:

- bad: `summary + repository + issue_number + changed + closed + url`
- good: `summary + url`

The goal is to keep authored success output compact, legible, and intentional rather than turning `publish` into a noisy dump of whatever the workflow happened to observe.

## Bootstrap sequence

The initial recommended bootstrap sequence is:

```bash
./ordo-help --json
./ordo-help overview --json
./ordo-help capabilities --json
./ordo-help model --json
./ordo-help command-line --json
./ordo-help operations --json
./ordo-help examples --json
```

This sequence should let a zero-knowledge caller discover:

- the purpose and scope of Ordo;
- the main supported and unsupported capability boundaries;
- the main authoring surfaces and contracts;
- the paired workflow-authoring passes for applicability (`check`) and authoring quality (`review`);
- the public launch-command surface for common entrypoints such as `ordo-playbook`;
- the public executable operation inventory.

## Boundary rule

`ordo-help` should translate runtime-owned introspection into a caller-friendly public vocabulary, but it should not become an alternate semantic source of truth.
