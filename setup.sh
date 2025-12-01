#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="ulma"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ_FILE="${SCRIPT_DIR}/requirements.txt"

# Locate conda
if ! command -v conda >/dev/null 2>&1; then
  echo "[ERROR] conda not found on PATH. Install Miniconda/Anaconda and reopen your shell."
  exit 1
fi

# Initialize conda
# shellcheck disable=SC1091
source "$(conda info --base)/etc/profile.d/conda.sh"

# --- Check if the environment exists ---
if conda env list | grep -qE "^[[:space:]]*${ENV_NAME}[[:space:]]"; then
  echo "Conda environment \"${ENV_NAME}\" already exists."
else
  echo "Creating environment \"${ENV_NAME}\"..."
  conda create -y -n "${ENV_NAME}" python=3.11
fi

# --- Activate the environment ---
conda activate "${ENV_NAME}"

# --- Install requirements ---
python -m pip install --upgrade pip
python -m pip install -r "${REQ_FILE}"

echo "Environment \"${ENV_NAME}\" is ready!"
