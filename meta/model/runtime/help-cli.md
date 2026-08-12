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
./ordo-help snippet-coverage [--json]
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
- `overview` should also explain that runtime diagnostics distinguish internal workflow/engine failures from external command or remote-system failures when that context is available.
- `capabilities` exposes supported, unsupported, and planned surface states.
- `model` aggregates the main authoring contracts over workflows, profiles, playbooks, and runtime state.
- `command-line` exposes the public launch-command surface, stable flag semantics, the distinct roles of `ordo-playbook check` and `ordo-playbook review`, and the normalized external-failure payload fields surfaced by `run --json` when runtime has that context.
- `operations` exposes the public connector operation catalog.
- `examples` exposes verified repository examples intended as public authoring references.
- `snippet-coverage` exposes which describable handles do and do not publish canonical verified snippets.
- `operation <reference>` exposes one focused operation contract.
- `describe <topic>` resolves a supported public topic, capability node, or model node to the same canonical discovery surface.
- `search <query>` helps a caller bridge from vague terms to public topics, published contract facts, or operation references.

## Canonical snippet coverage

`ordo-help describe` should publish explicit canonical-snippet coverage state for describable handles rather than forcing a caller to infer support from silence.

- Every describable handle should publish `snippet_coverage`, even when the value is `none`.
- Initial coverage states are:
  - `none`
  - `excerpt_verified`
  - `harness_verified`
- `canonical_examples` should list the short positive snippets published for that handle.
- Excerpt-backed snippets should identify their source example and excerpt location.
- Harness-backed snippets should identify the verification harness used to validate the minimal form.
- Snippet-world-backed examples should identify the teaching context and verification path used to keep the example strict.
- The help model may support more than one example form, such as value examples, step-field examples, step fragments, and workflow fragments.
- `describe` should surface enough metadata for a caller to distinguish those forms honestly rather than inferring them from the raw snippet text alone.
- The renderer must not silently disguise one verified example kind as a different authored shape just to make the output look friendlier.
- `snippet-coverage` should aggregate the current coverage map so a caller can tell where snippet support is still missing.

The goal is for `describe` to act as a short syntax confirmer for disputed authoring forms without turning prose examples into an unverified second source of truth.

Snippet worlds are publication and verification context for help examples, not runtime workflow semantics.
They provide stable shared teaching context for snippets that are too small to stand alone while preserving the invariant that the published example remains the example that was actually verified.

## Workflow authoring pass pair

When a caller is adding or changing a workflow, `ordo-help` should make the authoring loop explicit:

- `ordo-playbook check <workflow>` answers whether the workflow is applicable and execution-ready now.
- `ordo-playbook review <workflow>` answers whether the workflow has authoring-quality findings.
- `check` and `review` are complementary authoring passes; neither replaces the other.

The public help surface should present this pairing in at least the `overview`, `workflow-authoring`, and `command-line` topics so a zero-knowledge caller does not infer that `check` alone is sufficient workflow sign-off.

## External failure diagnostics

When runtime has normalized external command or remote-system context, public help should make that behavior discoverable instead of leaving it implicit.

- `overview` should state that user-facing diagnostics may distinguish internal workflow or engine failures from external causes.
- `command-line` should name the normalized external failure payload fields published through `run --json`.
- At minimum, the published external failure payload contract should mention: `kind`, `classification`, `tool`, `system`, `argv_summary`, `stderr_excerpt`, and `suggested_checks`.

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

## Local payload staging and result emission

`ordo-help workflow-authoring` should also make the workflow-local staging boundary explicit.

- Use `value + register` when one assembled payload must be reused by later steps through `step.<register>...` reads.
- Use `result` only to append one authored value to the workflow-local `results` list.
- Do not imply that `result` also creates a reusable registered binding.
- When a workflow needs both internal reuse and outward or final emission, stage first with `value + register`, then emit that staged value through `result` or `publish`.

The goal is to keep payload construction distinct from payload emission so authors do not treat `result` as a hidden variable-binding surface.

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
./ordo-help snippet-coverage --json
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
