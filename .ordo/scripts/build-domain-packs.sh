#!/usr/bin/env bash
set -euo pipefail

exec ".venv/bin/python" "tools/build_domain_packs.py" "meta/domain-packs.toml"
