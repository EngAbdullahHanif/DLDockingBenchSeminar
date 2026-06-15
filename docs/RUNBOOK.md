# Cluster runbook — KarmaDock prototype (team002)

Every step you run is below. Nothing here touches the cluster on its own — you
execute each step. Commands assume the Saarland HPC (`conduit`, HTCondor **docker
universe**). For the full command log incl. the LP/BDB bonus track, see
`RUN_COMMANDS.md`; this runbook covers the **prototype** (P1/P2/P3 on proto data).

Cluster: `ssh bdldt_team002@conduit.hpc.uni-saarland.de` (passwordless — this
laptop's key is in `authorized_keys`). Everything lives under
`$HOME = /home/bdldt_team002`:

```
~/run/
├── code/               this repo (scripts/, condor/, notebooks/, docker/)
├── data/proto/         proto_train/  proto_test/  proto_train.csv  proto_test.csv
├── work/               complex/  graphs/  ckpt/  kd_out/        (created by the jobs)
├── results/            <pipeline>/proto_test/*_pred.sdf         (predicted poses)
└── logs/               condor .out/.err/.log
```

All `condor/*.sub` use **absolute `/home/bdldt_team002/...` paths** in `arguments`
and run the scripts baked into the image at `/app/scripts/`. Data/outputs are on
the shared `/home` NFS mount (`+WantGPUHomeMounted = true`,
`should_transfer_files = NO`) — **no file transfer per job**.

---

## 0. One-time: build & push the Docker image (on this laptop)

This laptop is **Linux x86_64** and Docker is **rootful** (rootless is blocked by
AppArmor), so build with `sudo` and a native `linux/amd64` image — no cross-build
needed.

```bash
cd ~/Desktop/project/karmadock-seminar      # build context = repo root
sudo docker login -u ahlamloum
sudo docker build -t ahlamloum/karmadock-seminar:v4 -f docker/Dockerfile .
sudo docker push ahlamloum/karmadock-seminar:v4
```

- **Prototype subs pin `:v4`.** (The LP/BDB bonus subs pin `:v6` = v4 + the
  `--val_csv` / W&B-unique-run-id additions; rebuild that tag only if you touch
  `scripts/`.)
- The image installs the authors' **pre-packed** conda env (no solver), then
  `COPY`s our `scripts/` in a late layer, so script edits re-push in seconds.
- The build runs a sanity import of torch/torch_geometric/rdkit/MDAnalysis/prody,
  so a broken env fails the build, not a cluster job.

## 1. One-time: stage code + data on the cluster

```bash
# from this laptop — push the repo to ~/run/code
rsync -az --delete ~/Desktop/project/karmadock-seminar/ \
    bdldt_team002@conduit.hpc.uni-saarland.de:~/run/code/

# on the cluster — create the workspace and unzip the tutor's proto data
ssh bdldt_team002@conduit.hpc.uni-saarland.de
mkdir -p ~/run/data ~/run/work ~/run/results ~/run/logs
cd ~/run/data && unzip /path/to/prototype_model_data.zip   # -> proto/ with train/test + csvs
# the subs expect ~/run/data/proto/proto_{train,test}{,.csv}; adjust if the zip name differs
```

## 2. Preprocess (CPU): pockets + graphs — one sub per split

Two ready-made subs (absolute paths baked in — **no editing**):

```bash
cd ~/run/code/condor
condor_submit preprocess_train.sub     # -> work/graphs/proto_train
condor_submit preprocess_test.sub      # -> work/graphs/proto_test
condor_q -nobatch                       # watch; check logs/*.err on failure
```

Each runs `/app/scripts/preprocess.sh <csv> <src> <complex_out> <graph_out>`
(8 CPUs). Sanity check: `ls ~/run/work/graphs/proto_train/*.dgl | wc -l` — a few
hundred; some complexes drop when RDKit can't sanitise the ligand (expected).

## 3a. P1 — baseline inference (GPU), released weights

```bash
condor_submit p1_infer_baseline.sub
# docks proto_test with /app/KarmaDock/trained_models/karmadock_screening.pkl
# -> results/p1_baseline/proto_test/*_pred.sdf  +  work/kd_out/p1_baseline/proto_test/<re>.csv
```

This alone gives a complete, submittable predicted-poses set + the notebook plots.

## 3b. P2 / P3 — train our checkpoints (GPU)

**W&B (optional):** the key is passed at submit time via the `environment` line —
never stored in a file. Use your **rotated** key, not the old exposed one.

```bash
# P2 — from scratch (2-stage paper protocol)
condor_submit p2_train_scratch.sub
#   (offline/no-W&B: the sub has a commented `environment = "WANDB_MODE=offline WANDB_API_KEY=dummy"`)
# -> work/ckpt/p2_scratch/stage2_docking/karmadock_team002.pkl  (+ last.pt for --resume)

# P3 — fine-tune the released checkpoint, with W&B logging
condor_submit -a 'environment = "WANDB_API_KEY=<your_rotated_key>"' p3_finetune.sub
# -> work/ckpt/p3_finetune/karmadock_team002.pkl
```

`train.py` checkpoints every epoch with `--resume` on, so a force-reschedule
resumes from `last.pt`. Effective batch = 4 × 16 accum = 64 (args `... 4 16`).

## 3c. P2 / P3 — inference with OUR checkpoints (GPU)

```bash
condor_submit p2_infer.sub    # docks proto_test with the P2 scratch ckpt
condor_submit p3_infer.sub    # docks proto_test with the P3 fine-tune ckpt
# -> results/<pipeline>/proto_test/*_pred.sdf
```

## 4. Visualize + evaluate

```bash
# run on the cluster (data lives there), or locally with KD_BASE pointing at a mirror:
cd ~/run/code/notebooks
KD_BASE=~/run jupyter nbconvert --to notebook --execute --inplace results_and_comparison.ipynb
#   tables (succ@2Å, median RMSD), ECDF, training curves, PoseBusters, top-pose RMSD

# official metric — from the seminar repo root, on our submitted poses:
python evaluation/evaluation.py --dataset proto_test
```

## 5. Assemble the prototype submission (due 19 June)

- [ ] source code (this repo, documented) → GitHub `karmadock` branch
- [ ] training checkpoints → `work/ckpt/{p3_finetune,p2_scratch/stage2_docking}/karmadock_team002.pkl`
- [ ] results notebook → `notebooks/results_and_comparison.ipynb`
- [ ] predicted poses → `results/<pipeline>/proto_test/` (submit P1 uncorrected as the headline)
- [ ] Docker image name → `ahlamloum/karmadock-seminar:v4`
- [ ] Condor files → `condor/*.sub` **plus the `logs/*.{log,out,err}` from the real runs**

## Debugging quickies
- `condor_q -nobatch` — live jobs; `condor_q -hold <id>` — why a job is held
- `condor_q -better-analyze <id>` — why a job isn't matching / sits idle
- job stuck idle forever → usually an over-tight `requirements`/resource request
  (e.g. multi-GPU: our 2-GPU DDP smoke never scheduled)
- import errors in `logs/*.err` → image env wrong; fix Dockerfile, rebuild, repush
- training curve live: `tail -f ~/run/work/ckpt/<pipe>/stage2_docking/train_log.csv`
