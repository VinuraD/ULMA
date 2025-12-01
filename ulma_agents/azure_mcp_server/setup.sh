#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure python available
if ! command -v python >/dev/null 2>&1; then
  echo "[ERROR] python not found on PATH."
  exit 1
fi

cd "${SCRIPT_DIR}"
python server.py
