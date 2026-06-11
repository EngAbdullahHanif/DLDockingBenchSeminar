#!/bin/bash
# run_docking.sh - Docking script for HTCondor job
set -euo pipefail
set -x

DATASET=$1
CORRECT=${2:-True}

echo "=== KarmaDock Docking ==="
echo "Dataset: ${DATASET}"
echo "Correct: ${CORRECT}"
echo "GPU:     ${CUDA_VISIBLE_DEVICES:-None}"
echo "========================="

mkdir -p "docking_output/${DATASET}"
mkdir -p "results/${DATASET}"

# Step 1: Run docking
python3 /app/KarmaDock/utils/ligand_docking.py \
    --graph_file_dir "graphs/${DATASET}" \
    --model_file "/app/KarmaDock/trained_models/karmadock_screening.pkl" \
    --out_dir "docking_output/${DATASET}" \
    --docking True \
    --scoring True \
    --correct "${CORRECT}" \
    --batch_size 64 \
    --random_seed 2023

# Step 2: Format back to seminar predicted SDFs
MODE="align_corrected"
if [ "${CORRECT}" = "False" ]; then
    MODE="uncorrected"
fi

python3 scripts/convert_karmadock_to_seminar.py \
    --input_dir "docking_output/${DATASET}" \
    --csv "${DATASET}.csv" \
    --out_dir "results/${DATASET}" \
    --mode "${MODE}"

echo "=== Docking Completed Successfully ==="
