#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Expected virtualenv Python at $PYTHON_BIN. Create the virtualenv and install dependencies first." >&2
  exit 1
fi

cd "$PROJECT_ROOT"
exec "$PYTHON_BIN" -m src.main "$@"
