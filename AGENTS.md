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

## GitHub and project operations

- Prefer the corresponding `ordo-playbook` workflow for GitHub and project operations.
- GitHub writing rule: issue titles, bodies, comments, labels, and project field values must be in English only.
- Keep API responses lean: request only the fields needed for the decision.
