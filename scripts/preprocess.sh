#!/usr/bin/env bash
# preprocess.sh <seminar_csv> <refined_src_dir> <complex_out_dir> <graph_out_dir>
# Converts seminar data -> KarmaDock layout, extracts 12A pockets, builds .dgl graphs.
set -euo pipefail
set -x

CSV=$1; SRC=$2; COMPLEX=$3; GRAPH=$4
KD=/app/KarmaDock

mkdir -p "$COMPLEX" "$GRAPH"

# 1) seminar -> KarmaDock layout
python3 /app/scripts/convert_seminar_to_karmadock.py --csv "$CSV" --src_dir "$SRC" --out_dir "$COMPLEX"

# 2) pocket extraction (CPU; prody only, no Schrodinger needed)
cd "$KD/utils"
python3 -u pre_processing.py --complex_file_dir "$COMPLEX"

# 3) graph generation  (NOTE: upstream generate_graph.py takes NO --n_job flag)
python3 -u generate_graph.py --complex_file_dir "$COMPLEX" --graph_file_dir "$GRAPH"

echo "=== preprocess done: $(ls "$GRAPH" | wc -l) graphs in $GRAPH ==="
