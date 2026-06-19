#!/usr/bin/env bash
# run_finetune.sh <train_csv> <graph_dir> <complex_dir> <out_dir> [batch_size] [accum_steps]
#
# PIPELINE 3 — FINE-TUNE the released KarmaDock checkpoint on the seminar data.
# We start from the authors' trained weights (karmadock_screening.pkl) and continue
# training the docking+scoring model on the tutor split. Because the encoders + MDN are
# already trained, this is a single "stage-2-style" run (pos_r=1) with the paper's
# stage-2 hyperparameters: lr 1e-4, weight_decay 0, effective batch 64, split seed 42.
#
# Patience is set to 30 (not 70): fine-tuning a pretrained model on a small set converges
# fast and a shorter patience guards against overfitting the prototype split. Re-run with
# the full dataset later for the final-stage result.
#
# Checkpoints every epoch + --resume => reschedule-safe. W&B only if WANDB_API_KEY is set.
set -euo pipefail
set -x

CSV=$1; GRAPH=$2; COMPLEX=$3; OUT=$4; BS=${5:-8}; ACC=${6:-8}; VAL=${7:-}; VALGRAPH=${8:-}
export PYTHONPATH=/app/KarmaDock:${PYTHONPATH:-}
mkdir -p "$OUT"

WB=""
if [ -n "${WANDB_API_KEY:-}" ]; then WB="--wandb --wandb_project karmadock-seminar"; fi
# Optional args 7/8: explicit validation CSV + its graph dir (LP-PDBBind's leak-proof val
# split, preprocessed separately). When set we pass --val_csv/--val_graph_dir and train.py
# uses ALL of $CSV for training; when empty it falls back to the deterministic --val_frac
# split used by the prototype P3 run.
VALARG=""; if [ -n "$VAL" ]; then VALARG="--val_csv $VAL"; fi
if [ -n "$VALGRAPH" ]; then VALARG="$VALARG --val_graph_dir $VALGRAPH"; fi
RUN_NAME="p3_finetune"; if [ -n "$VAL" ]; then RUN_NAME="p4_lp_finetune"; fi

python3 -u /home/bdldt_team002/run/code/scripts/train.py \
    --csv "$CSV" --graph_dir "$GRAPH" --complex_dir "$COMPLEX" --out_dir "$OUT" \
    --init_model /app/KarmaDock/trained_models/karmadock_screening.pkl \
    --pos_r 1 --lr 1e-4 --weight_decay 0 \
    --batch_size "$BS" --accum_steps "$ACC" --patience 30 --epochs 500 \
    --val_frac 0.1 --random_seed 42 --resume $VALARG \
    $WB ${WB:+--wandb_run_name $RUN_NAME}

echo "=== P3 (fine-tune) done. fine-tuned checkpoint: $OUT/karmadock_team002.pkl ==="
