#!/usr/bin/env bash

set -euo pipefail

export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [[ -s "$NVM_DIR/nvm.sh" ]]; then
  # shellcheck source=/dev/null
  source "$NVM_DIR/nvm.sh" --no-use
fi

if ! type nvm >/dev/null 2>&1; then
  echo "error: nvm is required for frontend set-active-task" >&2
  exit 1
fi

nvm use >/dev/null
npm run openapi
npm run errors:sync
npm run check

if ! git diff --quiet || ! git diff --cached --quiet; then
  git add -A
  git commit -m "chore(openapi): regenerate api types"
fi
