#!/bin/bash
# run_preprocessing.sh - Preprocessing script for HTCondor job
set -euo pipefail
set -x

DATASET=$1
N_JOB=${2:-4}

echo "=== KarmaDock Preprocessing ==="
echo "Dataset: ${DATASET}"
echo "Jobs:    ${N_JOB}"
echo "=============================="

# Create directories
mkdir -p karmadock_input/${DATASET}
mkdir -p graphs/${DATASET}

# Step 1: Format dataset
echo "Converting seminar data format to KarmaDock layout..."
python3 scripts/convert_seminar_to_karmadock.py \
    --csv "${DATASET}.csv" \
    --src_dir "${DATASET}" \
    --out_dir "karmadock_input/${DATASET}"

# Step 2: Pocket extraction
echo "Extracting protein pockets..."
python3 /app/KarmaDock/utils/pre_processing.py \
    --complex_file_dir "karmadock_input/${DATASET}"

# Step 3: Graph generation
echo "Generating graphs..."
python3 /app/KarmaDock/utils/generate_graph.py \
    --complex_file_dir "karmadock_input/${DATASET}" \
    --graph_file_dir "graphs/${DATASET}" \
    --n_job "${N_JOB}"

echo "=== Preprocessing Completed Successfully ==="
