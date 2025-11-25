#!/bin/bash

ENV_NAME="ulma"

# Load conda functions
source "$(conda info --base)/etc/profile.d/conda.sh"

# --- Check if the environment exists ---
if conda env list | grep -q "^$ENV_NAME "; then
    echo "Conda environment \"$ENV_NAME\" already exists."
else
    echo "Creating environment \"$ENV_NAME\"..."
    conda create -y -n "$ENV_NAME" python=3.11
fi

# --- Activate the environment ---
conda activate "$ENV_NAME"

# --- Install requirements ---
pip install -r requirements.txt

echo "Environment \"$ENV_NAME\" is ready!"
