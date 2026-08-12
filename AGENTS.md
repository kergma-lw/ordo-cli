# AGENTS

## Meta source layout

- `meta/` source docs are organized first by document type, then by domain.
- Use domain-named subdirectories such as:
  - `meta/requirements/connector/`
  - `meta/model/runtime/`
  - `meta/data/workflow/`
  - `meta/verification/meta/`
- `meta/packs/` is the primary read surface for compact review.
- Optimize source docs for accurate maintenance of domain boundaries, not for single-file reading.

## Authoring rules

- All project documentation must be written in English.
- Issue text and issue comments must also be written in English.
- Avoid generic catch-all glossary files.
- Put terminology next to the domain it belongs to, for example in `meta/domain/connector.md`.
- Keep connector concerns, workflow concerns, runtime concerns, and policy concerns separated.
- Do not change `meta/` source truth merely to fit the current code shape without explicit user discussion and agreement.
- If code and `meta/` disagree, treat it as a drift signal to investigate first rather than silently rewriting the meta docs.
- Do not edit `meta/packs/**` by hand; regenerate them from source docs.
- After changing `meta/` source docs, regenerate `meta/packs/**` in the same work so derived artifacts stay in sync.
- Regenerate `meta/packs/**` via `ordo-playbook run meta-packs-build`.

## Python environment

- The project-local virtual environment is `/home/ww/projects/ordo/.venv`.
- Create or recreate this environment with `/usr/bin/python3.12 -m venv /home/ww/projects/ordo/.venv`.
- Use this environment for testing, local runs, dependency installation, and other Python-based project commands.
- Prefer invoking tools through the virtual environment explicitly, for example `/home/ww/projects/ordo/.venv/bin/python`, or activate it before running project commands.

## Operational workflows (Ordo-first)

- `ordo-playbook` is the canonical operational entrypoint.
- If a suitable workflow exists, do not use a direct command instead of it.
- `ordo-playbook` command modes from `--help`:
  - Discovery: `workflows`
  - Execution: `review`, `check`, `plan`, `explain`, `run`, `next`
- Example:
  - inspect available workflows: `ordo-playbook workflows list`
  - execute a workflow: `ordo-playbook run <workflow>`
- Use `ordo-playbook workflows list` as the default discovery surface.
- If a suitable `ordo-*`/`ordo-playbook` workflow exists, run it directly.
- Do not run unrelated preflight shell commands (`ls`, `pwd`, ad-hoc env checks, etc.) before an Ordo workflow unless they are strictly required for the workflow to succeed or the user explicitly asked for them.
- Prefer the minimal command sequence that answers the user request.
- Do not improvise operational entrypoints from memory or by guessing the most likely shell command.
- Hard rule: do not replace a missing or unknown workflow with a self-chosen “obvious” direct command (`gh`, `git`, `npm`, `python`, helper script, ad-hoc one-liner, etc.) just because the intent seems clear.
- If no suitable workflow exists yet:
  - use `.AGENTS.md.pre-ordo-backup` only as reference material;
  - inspect the current Ordo help/discovery surface;
  - propose how the missing workflow should look;
  - discuss it with the user before executing any legacy ritual directly.
- Do not treat legacy helper scripts or TUI commands as the primary interface.
- A direct command or temporary legacy bypass is allowed only when the user explicitly asks for it or explicitly approves the bypass.

## Engine change discipline

- Treat engine changes as contract changes, not isolated code edits.
- Any change to engine, runtime, workflow-model, execution, validation, planning, review, explanation, next-step selection, introspection, or other behavior-bearing core code must review its impact on all public runtime modes:
  - `check`
  - `review`
  - `plan`
  - `run`
  - `explain`
  - `next`
- If the change affects any of those modes, update the affected behavior, diagnostics, or published semantics in the same work.
- Do not assume that updating one mode is sufficient just because the touched code path looks local; review the full mode surface explicitly.

### Discovery and help parity

- Engine changes must also review their impact on the public discovery surface.
- If a change affects authoring meaning, recommended usage, applicability, validation rules, diagnostics, public handles, runtime semantics, fallback semantics, or other user-visible behavior, review and update the affected discovery surfaces in the same work.
- This includes, when relevant:
  - `ordo-help features`
  - `ordo-help overview`
  - `ordo-help model`
  - `ordo-help workflow-authoring`
  - `ordo-help capabilities`
  - `ordo-help command-line`
  - `ordo-help operations`
  - `ordo-help describe ...`
  - `ordo-help search ...`
- Do not treat discovery or help updates as optional polish. They are part of the published behavior contract.

### Features parity

- `ordo-help features` is the compact workflow-authoring feature map for authors and agents.
- Any engine change that affects workflow authoring surfaces, discoverability, named primitives, fallback paths, recommended patterns, discouraged patterns, or cluster boundaries must review and update `ordo-help features` in the same work.
- If a new or changed behavior exists but is not surfaced correctly in `ordo-help features`, the change is incomplete.

### Snippet-backed example parity

- After completing a task that changes a public authoring or discovery surface, review whether any relevant snippet-backed examples must be updated in the same work.
- This applies to help surfaces such as `ordo-help describe ...`, `ordo-help workflow-authoring`, `ordo-help features`, and other published discovery output that teaches or confirms authored shapes.
- Any task that changes one or more public `ordo-help describe ...` surfaces must explicitly run those affected describe surfaces against the describe readiness checklist and treat that review as part of the work, not as optional follow-up polish.
- If one or more affected describe surfaces do not satisfy the checklist cleanly, discuss the gap before closing the work instead of silently accepting a half-ready describe surface.
- If a relevant verified snippet already exists for the affected surface, update it in the same work so the published example stays aligned with the implemented behavior.
- If no relevant snippet exists but the supported snippet-world path can represent the changed surface honestly, add the missing snippet in the same work rather than treating snippet coverage as optional follow-up polish.
- If the supported snippet-world path does not yet support the required example shape, do not silently ignore the gap.
- In that case, explicitly call out the unsupported snippet shape as a problem before closing the work, because the lack of snippet support is now blocking accurate help parity.
- Do not paper over the gap with decorative rendering tricks, silently transformed examples, or unverifiable prose that pretends to be a real snippet.
- Snippet updates belong to the same parity discipline as help text updates: if the public surface changed, the relevant verified examples must change with it, or the work is incomplete.

### Ambiguity requires discussion

- For engine changes, ambiguity is a stop signal, not a license to guess.
- If it is unclear whether or how a change should affect `check` / `review` / `plan` / `run` / `explain` / `next`, discuss it before implementation or, at the latest, before considering the change complete.
- If it is unclear whether or how discovery surfaces should change, discuss it before implementation or before closure.
- If the semantic radius of the change is broad, cross-cutting, or difficult to propagate confidently, prefer discussion over silent completion.
- Do not close an engine change on guessed parity.
- When in doubt, raise the discussion earlier rather than silently shipping a partial interpretation.

### Completion rule

- An engine change is not complete until all affected runtime modes and all affected discovery/help surfaces have been reviewed and updated together, or their non-impact has been explicitly established.
- After a work item is otherwise complete, run `ordo-playbook run verify-all-tests` before final closure.

## GitHub and project operations

- Prefer the corresponding `ordo-playbook` workflow for GitHub and project operations.
- GitHub writing rule: issue titles, bodies, comments, labels, and project field values must be in English only.
- Keep API responses lean: request only the fields needed for the decision.
