# RUN_COMMANDS.md — every command used to run / train / infer / evaluate

Consolidated, copy-pasteable log of the commands behind each pipeline, with the **effective
hyperparameters** (resolved from the wrapper scripts). Secrets are shown as placeholders.
Cluster: `ssh bdldt_team002@conduit.hpc.uni-saarland.de`; workspace `~/run/` (`code/ data/ work/ results/ logs/`).
Image: `ahlamloum/karmadock-seminar:v6` (was v4/v5 earlier). All training/inference runs in the
HTCondor **docker universe**; data/outputs on the shared `/home` mount (`+WantGPUHomeMounted`).

Convention: `<WANDB_KEY>` = the W&B API key (passed at submit time, never stored in a file).

---

## 0. Image build (local laptop, x86_64; root logged into Docker Hub)
```bash
cd <repo>                       # build context = repo root
sudo docker build -t ahlamloum/karmadock-seminar:v6 -f docker/Dockerfile .
sudo docker push ahlamloum/karmadock-seminar:v6
# v5/v6 only re-push the scripts layer (base/conda/pip layers cached). v6 = v5 + W&B-unique-id fix.
```

## 1. Data prep (run on the cluster login node)

### PDBBind v2020 download + extract (for LP train/val/test)
```bash
bash ~/fetch_pdbbind.sh         # wget the 3 official archives, gzip -t, tar -xzf
# -> ~/run/data/pdbbind/extracted/{v2020-other-PL, refined-set}
# URLs (no subscription): https://static.pdbbind-plus.org.cn/v2020-renew_website/
#   PDBbind_v2020_{plain_text_index,other_PL,refined}.tar.gz
```

### LP-PDBBind adapter -> seminar-format splits (stdlib; runs on bare login node)
```bash
python3 ~/run/code/scripts/lp_to_seminar.py \
    --lp_csv ~/run/data/lp_PDBBind.csv \
    --pdbbind_dir ~/run/data/pdbbind/extracted \
    --out_dir ~/run/data/lp
# defaults (paper protocol): --train_clean CL1 --test_clean CL2, drop covalent.
# -> lp_{train,val,test}.csv + lp_{train,val,test}/<id>_ligand_refined.sdf/_protein_refined.pdb
# Result: 7393 train / 1891 val / 2171 test (0 dropped).
```

### BDB2020+ adapter (honest external test, in-repo tarball)
```bash
tar -xzf ~/run/data/BDB2020+.tgz -C ~/run/data
python3 ~/run/code/scripts/bdb_to_seminar.py --bdb_root ~/run/data/BDB2020+ --out_dir ~/run/data
# -> ~/run/data/bdb2020.csv + ~/run/data/bdb2020/<ID>_ligand_refined.sdf/_protein_refined.pdb  (136)
```

## 2. Preprocess (CPU): seminar data -> 12A pockets -> .dgl graphs
Executable in every preprocess sub = `/app/scripts/preprocess.sh <csv> <src_dir> <complex_out> <graph_out>`.
```bash
cd ~/run/code/condor
condor_submit preprocess_lp_train.sub     # -> work/graphs/lp_train  (6377/7393 kept)
condor_submit preprocess_lp_val.sub       # -> work/graphs/lp_val    (1552/1891)
condor_submit preprocess_lp_test.sub      # -> work/graphs/lp_test   (1862/2171)
condor_submit preprocess_bdb.sub          # -> work/graphs/bdb2020   (135/136)
# (proto_train / proto_test graphs were built in earlier sessions via preprocess_{train,test}.sub)
# ~15% drop = RDKit ligand-sanitisation (kekulize/valence) failures on raw PDBBind sdf; expected.
```
**Workaround when cluster CPU queue is jammed — preprocess locally via the image, ship graphs up:**
```bash
python3 scripts/bdb_to_seminar.py --bdb_root <BDB2020+> --out_dir bdb_local --copy
sudo docker run --rm -v "$PWD/bdb_local:/data" ahlamloum/karmadock-seminar:v6 \
    bash /app/scripts/preprocess.sh /data/bdb2020.csv /data/bdb2020 /data/complex/bdb2020 /data/graphs/bdb2020
sudo chown -R "$USER" bdb_local
rsync -az bdb_local/graphs/bdb2020/ <cluster>:~/run/work/graphs/bdb2020/
```

## 3. Training

### P4 — LP fine-tune (1 GPU) — released ckpt fine-tuned on LP CL1-train
```bash
cd ~/run/code/condor
condor_submit -a 'environment = "WANDB_API_KEY=<WANDB_KEY>"' p4_lp_finetune.sub
```
Executable `/app/scripts/run_finetune.sh`, args `lp_train.csv graphs/lp_train complex/lp_train ckpt/p4_lp_finetune 4 16 lp_val.csv graphs/lp_val`, resolving to:
```
train.py --init_model /app/KarmaDock/trained_models/karmadock_screening.pkl \
         --pos_r 1 --lr 1e-4 --weight_decay 0 --batch_size 4 --accum_steps 16 \
         --patience 30 --epochs 500 --val_frac 0.1 --random_seed 42 --resume \
         --val_csv lp_val.csv --val_graph_dir graphs/lp_val   (effective batch 64)
```
Result: early-stopped epoch 30, best @ epoch 0 (val_rmsd ~2.62; fine-tune ~= released weights).

### P5 — LP from-scratch (single GPU, 2-stage paper protocol)
```bash
condor_submit -a 'environment = "WANDB_API_KEY=<WANDB_KEY>"' p5_lp_scratch_1gpu.sub
```
Executable `/app/scripts/run_train_lp_scratch.sh` (home-mounted), args `lp_train.csv graphs/lp_train complex/lp_train ckpt/p5_lp_scratch lp_val.csv 4 16 graphs/lp_val`, resolving to:
```
# Stage 1 (scoring/MDN):  train.py --init_model "" --pos_r 0 --lr 1e-3 --weight_decay 1e-5 \
#     --batch_size 4 --accum_steps 16 --patience 70 --epochs 1000 --random_seed 42 --resume \
#     --val_csv lp_val.csv --val_graph_dir graphs/lp_val
# Stage 2 (docking+scoring, init from stage1 best): train.py --init_model stage1/karmadock_team002.pkl \
#     --pos_r 1 --lr 1e-4 --weight_decay 0 --batch_size 4 --accum_steps 16 --patience 70 --epochs 1000 ...
```
Single-GPU chosen after the 2-GPU/DDP request sat un-schedulable >6 h. Stage-1 early-stopped epoch 165 (best@95); stage-2 ongoing.
**Multi-GPU variant** (`p5_lp_scratch.sub`, request_gpus=4) launches the same wrapper via `torchrun --standalone --nproc_per_node=$NGPU` (DDP); needs a node with N free GPUs.

### P5 DDP smoke (2 GPU) + P5 single-GPU smoke (safeguards)
```bash
condor_submit -a 'environment = "WANDB_API_KEY=<WANDB_KEY>"' p5_ddp_smoke.sub   # 2-GPU; never scheduled
condor_submit p5_smoke_1gpu.sub                                                 # env EPOCHS=2 PATIENCE=2
# the 1-GPU smoke validated stage1->stage2 handoff + checkpointing before the real multi-day run.
```

### (prototype, earlier sessions) P2 from-scratch / P3 fine-tune on proto_train
```bash
condor_submit p2_train_scratch.sub        # run_train_paper.sh: 2-stage, patience 70, effective batch 64, seed 42
condor_submit -a 'environment = "WANDB_API_KEY=<WANDB_KEY>"' p3_finetune.sub   # run_finetune.sh: pos_r 1, lr 1e-4, patience 30
```

## 4. Inference + evaluation  (run_infer.sh = ligand_docking.py + convert)
Every infer sub executable = `/app/scripts/run_infer.sh <test_csv> <graph_dir> <model_file> <kd_out_dir> <results_dir>`, resolving to:
```
ligand_docking.py --graph_file_dir <graphs> --model_file <ckpt> --out_dir <kd_out> \
                  --docking True --scoring True --correct True --batch_size 64 --random_seed 2023
convert_karmadock_to_seminar.py --input_dir <kd_out> --csv <test_csv> --out_dir <results> --mode align_corrected
# kd_out CSVs hold ALL pose variants: RMSD (uncorrected) / FF_RMSD / Aligned_RMSD.
```
```bash
cd ~/run/code/condor
condor_submit p4_lp_infer.sub      # P4 on lp_test  (1862)  -> 94.5% @2A uncorrected (LEAKED, see TO_REVIEW_LATER.md)
condor_submit p4_proto_infer.sub   # P4 on proto_test (75)  -> 54.7% @2A uncorrected
condor_submit p1_bdb_infer.sub     # P1 baseline on BDB2020+ (135) -> 44.4% @2A uncorrected
condor_submit p4_bdb_infer.sub     # P4 on BDB2020+ (135)         -> 40.0% @2A uncorrected
condor_submit p5_lp_infer.sub      # P5 on lp_test    (after P5 trains)  [valid leak-proof number]
condor_submit p5_proto_infer.sub   # P5 on proto_test (after P5 trains)
# (prototype, earlier) p1_infer_baseline.sub / p2_infer.sub / p3_infer.sub on proto_test
```

## 5. Quick login-node eval (no pandas needed) — success@2A from kd_out CSVs
```bash
python3 - <<'PY'
import glob, csv, statistics
cols=["RMSD","FF_RMSD","Aligned_RMSD"]           # uncorrected / FF / align
d="/home/bdldt_team002/run/work/kd_out/<tag>/<testset>"
best={c:{} for c in cols}
for f in glob.glob(d+"/*.csv"):
    if not f.split("/")[-1][:-4].isdigit(): continue
    for r in csv.DictReader(open(f)):
        for c in cols:
            try: v=float(r[c])
            except: continue
            if v<999: best[c][r["pdb_id"]]=min(best[c].get(r["pdb_id"],1e9),v)
for c in cols:
    b=best[c]; n=len(b) or 1
    print(c, "success@2A=%.1f%%"%(100*sum(x<=2 for x in b.values())/n), "n=", len(b))
PY
```

## 6. Full formatted analysis (bootstrap CIs, paired tests, paper comparison)
```bash
# on the cluster (data lives there); or locally with KD_BASE=run_mirror
cd ~/run/code/notebooks
KD_BASE=~/run jupyter nbconvert --to notebook --execute --inplace analysis_and_comparison.ipynb
# data_exploration.ipynb similarly (dataset sizes, leakage, ligand props, attrition).
```

## 7. Monitoring helpers
```bash
ssh bdldt_team002@conduit.hpc.uni-saarland.de 'condor_q -nobatch'                 # live jobs
ssh ... 'condor_history <ClusterId> -af ExitCode JobStatus'                       # finished job exit
ssh ... 'tail -f ~/run/work/ckpt/<pipe>/stage2_docking/train_log.csv'             # training curve
ssh ... 'condor_q -better-analyze <ClusterId>'                                    # why a job is idle
```
