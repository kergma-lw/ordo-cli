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
- Do not edit `meta/packs/**` by hand; regenerate them from source docs.
- After changing `meta/` source docs, regenerate `meta/packs/**` in the same work so derived artifacts stay in sync.
- Regenerate packs with `python3 tools/build_domain_packs.py meta/domain-packs.toml`.
- Verify generated packs with `python3 tools/build_domain_packs.py meta/domain-packs.toml --check`.

## Python environment

- The project-local virtual environment is `/home/ww/projects/ordo/.venv`.
- Create or recreate this environment with `/usr/bin/python3.12 -m venv /home/ww/projects/ordo/.venv`.
- Use this environment for testing, local runs, dependency installation, and other Python-based project commands.
- Prefer invoking tools through the virtual environment explicitly, for example `/home/ww/projects/ordo/.venv/bin/python`, or activate it before running project commands.
