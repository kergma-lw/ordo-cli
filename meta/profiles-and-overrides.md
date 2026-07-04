# Profiles and overrides

## Profiles

A profile is not a new connector operation; it is a composition layer.

Named profile discovery and project-local profile catalogs may be owned by the playbook launch surface.
That launch surface does not change what a profile is; it only gives project-local names and selects the active profile for a playbook run.

It exists for:
- parameter presets;
- common verification sets;
- project and repo defaults;
- reducing duplication in workflows.

Examples:
- `backend-default`
- `frontend-check`
- `release-publication`

## Overrides

Local overrides are needed because Ordo is designed as a shared base plus local adaptation.

But there is a boundary:
- an override must be explicit;
- it must not silently break portability or readability.

## Preferred policy

- composition and parameters should go through profiles;
- new project-specific operations should go through a local namespace;
- same-name shadowing of base connector operations must not be default behavior.

## Why

Otherwise the workflow stops being self-describing:
the name suggests one thing while execution does another.
