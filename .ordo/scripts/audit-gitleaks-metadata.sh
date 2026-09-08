#!/bin/sh
# Use the repository-local environment without relying on shell activation.
set -eu
script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
python="$script_dir/../../.venv/bin/python"
if [ ! -x "$python" ]; then
    printf '%s\n' '{"status":"incomplete","code":"python_unavailable"}'
    exit 2
fi
exec "$python" "$script_dir/audit-gitleaks-metadata.py"
