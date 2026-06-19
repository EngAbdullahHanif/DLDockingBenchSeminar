#!/usr/bin/env bash
# run_train_paper.sh <train_csv> <graph_dir> <complex_dir> <out_dir> [batch_size] [accum_steps]
#
# PIPELINE 2 — full retrain FROM SCRATCH following the KarmaDock paper's two-stage
# "Training protocol" (Nat. Comput. Sci. 2023, Methods, p.801):
#
#   Stage 1  (scoring / MDN only):  pos_r=0  -> the model's forward skips the EGNN
#            docking module and optimises only the MDN scoring loss (+ the intended
#            atom/bond aux terms). Adam, lr 1e-3, weight_decay 1e-5, early-stop after
#            70 epochs without val improvement.
#   Stage 2  (docking + scoring):   pos_r=1  -> adds the RMSD docking loss with weight 1
#            and trains the EGNN jointly with the scoring module, INITIALISED from
#            Stage 1's best checkpoint. Same settings except lr 1e-4 and weight_decay 0.
#
# Both stages: effective batch 64 (= batch_size * accum_steps), train/val split seed 42.
# Each stage checkpoints every epoch and supports --resume, so the cluster job is safe
# against force-reschedules. A `stage.done` sentinel stops Stage 1 from re-running once
# it has converged when the whole job is rescheduled.
#
# W&B: enabled only if WANDB_API_KEY is set in the environment (otherwise train.py still
# writes train_log.csv locally, which is all the results notebook needs).
set -euo pipefail
set -x

CSV=$1; GRAPH=$2; COMPLEX=$3; OUT=$4; BS=${5:-8}; ACC=${6:-8}
export PYTHONPATH=/app/KarmaDock:${PYTHONPATH:-}

S1="$OUT/stage1_scoring"
S2="$OUT/stage2_docking"
mkdir -p "$S1" "$S2"

WB=""
if [ -n "${WANDB_API_KEY:-}" ]; then WB="--wandb --wandb_project karmadock-seminar"; fi

# ---- Stage 1: scoring / MDN (EGNN docking skipped via pos_r 0) ----
if [ ! -f "$S1/stage.done" ]; then
  python3 -u /app/scripts/train.py \
      --csv "$CSV" --graph_dir "$GRAPH" --complex_dir "$COMPLEX" --out_dir "$S1" \
      --init_model "" --pos_r 0 --lr 1e-3 --weight_decay 1e-5 \
      --batch_size "$BS" --accum_steps "$ACC" --patience 70 --epochs 1000 \
      --val_frac 0.1 --random_seed 42 --resume \
      $WB ${WB:+--wandb_run_name p2_stage1_scoring}
  touch "$S1/stage.done"
fi

# ---- Stage 2: docking + scoring, initialised from Stage 1 best ----
python3 -u /app/scripts/train.py \
    --csv "$CSV" --graph_dir "$GRAPH" --complex_dir "$COMPLEX" --out_dir "$S2" \
    --init_model "$S1/karmadock_team002.pkl" --pos_r 1 --lr 1e-4 --weight_decay 1e-4 \
    --batch_size "$BS" --accum_steps "$ACC" --patience 20 --epochs 1000 \
    --val_frac 0.1 --random_seed 42 --resume --jitter 0.05 \
    $WB ${WB:+--wandb_run_name p2_stage2_docking}

echo "=== P2 (from-scratch) done. final checkpoint: $S2/karmadock_team002.pkl ==="
