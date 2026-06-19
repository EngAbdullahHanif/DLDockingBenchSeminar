#!/usr/bin/env bash
# run_infer.sh <test_csv> <graph_dir> <model_file> <kd_out_dir> <results_dir>
# Runs KarmaDock docking+scoring with FF/align correction, then exports seminar SDFs.
set -euo pipefail
set -x

CSV=$1; GRAPH=$2; MODEL=$3; KDOUT=$4; RESULTS=$5
KD=/app/KarmaDock
mkdir -p "$KDOUT" "$RESULTS"

# 1) docking + scoring + pose correction (paper-recommended FF/align correction = --correct True)
cd "$KD/utils"
python3 -u ligand_docking.py \
    --graph_file_dir "$GRAPH" \
    --model_file "$MODEL" \
    --out_dir "$KDOUT" \
    --docking True \
    --scoring True \
    --correct True \
    --batch_size 64 \
    --random_seed 2023

# 2) export to seminar predicted-pose layout (best pose first)
python3 /home/bdldt_team002/run/code/scripts/convert_karmadock_to_seminar.py \
    --input_dir "$KDOUT" \
    --csv "$CSV" \
    --out_dir "$RESULTS" \
    --mode align_corrected

echo "=== inference done. predicted poses in $RESULTS ==="
