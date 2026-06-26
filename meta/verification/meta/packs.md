# Pack verification

## Rule

Generated files under `meta/packs/` must never be edited by hand.

Regenerate packs with `python3 tools/build_domain_packs.py meta/domain-packs.toml`.

## Check mode

The pack builder must support a `--check` mode that fails when generated output differs from committed output.

Verification command:

`python3 tools/build_domain_packs.py meta/domain-packs.toml --check`
