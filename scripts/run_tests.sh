#!/usr/bin/env bash
# Run the full unit test suite from the project root.

set -euo pipefail

cd "$(dirname "$0")/.."

if [ -x "venv/bin/python" ]; then
  PYTHON="venv/bin/python"
elif [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
else
  echo "[run_tests] Python not found. Create a venv or install python3." >&2
  exit 1
fi

echo "[run_tests] Using ${PYTHON}"
"${PYTHON}" -m unittest discover -v
