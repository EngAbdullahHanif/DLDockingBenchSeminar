#!/usr/bin/env bash
# run_full_pipeline.sh - Run the complete KarmaDock pipeline
set -euo pipefail

# Print commands for debugging
set -x

if [ "$#" -lt 3 ]; then
    echo "Usage: $0 <dataset_csv> <dataset_dir> <output_dir> [n_job] [correct_flag]"
    echo "Example: $0 proto_test.csv proto_test/ results/proto_test/ 4 True"
    exit 1
fi

DATASET_CSV=$1
DATASET_DIR=$2
OUTPUT_DIR=$3
N_JOB=${4:-4}
CORRECT=${5:-True}

echo "=== KarmaDock Pipeline Started ==="
echo "Dataset CSV: ${DATASET_CSV}"
echo "Dataset Dir: ${DATASET_DIR}"
echo "Output Dir:  ${OUTPUT_DIR}"
echo "CPUs/Jobs:   ${N_JOB}"
echo "Correct Poses: ${CORRECT}"
echo "GPU visible: ${CUDA_VISIBLE_DEVICES:-None}"
echo "=================================="

# Create temporary working directories
SCRATCH_DIR=$(mktemp -d -t karmadock-pipeline-XXXXXX)
# Clean up temp directories on exit
trap 'rm -rf "$SCRATCH_DIR"' EXIT

KARMADOCK_INPUT="${SCRATCH_DIR}/karmadock_input"
GRAPHS_DIR="${SCRATCH_DIR}/graphs"
DOCKING_OUT="${SCRATCH_DIR}/docking_output"

mkdir -p "${KARMADOCK_INPUT}" "${GRAPHS_DIR}" "${DOCKING_OUT}"

# Step 1: Format dataset to KarmaDock structure
echo "Step 1: Converting seminar data format to KarmaDock layout..."
python3 scripts/convert_seminar_to_karmadock.py \
    --csv "${DATASET_CSV}" \
    --src_dir "${DATASET_DIR}" \
    --out_dir "${KARMADOCK_INPUT}"

# Step 2: Pocket extraction (pre-processing)
echo "Step 2: Extracting protein pockets..."
python3 /app/KarmaDock/utils/pre_processing.py \
    --complex_file_dir "${KARMADOCK_INPUT}"

# Step 3: Graph generation
echo "Step 3: Generating graphs..."
python3 /app/KarmaDock/utils/generate_graph.py \
    --complex_file_dir "${KARMADOCK_INPUT}" \
    --graph_file_dir "${GRAPHS_DIR}" \
    --n_job "${N_JOB}"

# Step 4: Ligand Docking (Inference)
echo "Step 4: Running docking and scoring..."
# Check if CUDA is available, otherwise default to CPU
python3 /app/KarmaDock/utils/ligand_docking.py \
    --graph_file_dir "${GRAPHS_DIR}" \
    --model_file /app/KarmaDock/trained_models/karmadock_screening.pkl \
    --out_dir "${DOCKING_OUT}" \
    --docking True \
    --scoring True \
    --correct "${CORRECT}" \
    --batch_size 64 \
    --random_seed 2023

# Step 5: Convert outputs back to seminar format
echo "Step 5: Formatting results for seminar evaluation..."
# Use uncorrected if correct is False, otherwise try align_corrected (with fallback)
MODE="align_corrected"
if [ "${CORRECT}" = "False" ]; then
    MODE="uncorrected"
fi

python3 scripts/convert_karmadock_to_seminar.py \
    --input_dir "${DOCKING_OUT}" \
    --csv "${DATASET_CSV}" \
    --out_dir "${OUTPUT_DIR}" \
    --mode "${MODE}"

echo "=== KarmaDock Pipeline Completed Successfully ==="
