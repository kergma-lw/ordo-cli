# Repository hygiene

## Local generated and editor-only artifacts

The repository intentionally ignores a narrow set of local artifacts that do not belong in source control:

- `.ordo/repo.json` as local playbook state material;
- editor swap files such as `*.swp`.

## Rationale

These files create status noise without contributing to the shared runtime, workflow, or meta contract.

Ignoring them keeps repository status focused on authored source truth rather than on local tool residue.

## Scope discipline

This hygiene policy is intentionally narrow.

It does not broadly ignore arbitrary generated files; it only suppresses local artifacts that are clearly machine-local or editor-local and that should never be reviewed as part of the project contract.
