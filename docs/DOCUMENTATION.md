# KarmaDock seminar — project write-up & reproducibility guide

**Team 002 (KarmaDock) — Benchmarking DL-based Docking Tools, SS2026**

This is the document I wish I'd had when I started. It explains, in plain language, what
we built, why we built it that way, how every script works, and exactly how the whole
thing runs on the Saarland HPC cluster so that someone else (or future-me) can reproduce
it end to end. I've tried to write it the way I'd explain it to a labmate, not like a
manual.

---

## 1. What we're actually trying to do

The seminar gives every team one DL docking tool and asks: *if you retrain it on a
common dataset under standardized conditions, how good is it really?* The point is that
published docking papers all train on slightly different data, so you can't fairly
compare them. By retraining everyone's tool on the **same** split, the comparison becomes
fair.

Our tool is **KarmaDock**. We were given a small "prototype" dataset now
(`prototype_model_data`: ~712 training complexes, ~118 test complexes) and we'll get the
full dataset later. So everything here is the prototype dry-run; the same machinery will
just be pointed at the bigger data afterwards.

We decided to run **three pipelines** so we can actually see where performance comes from:

| Pipeline | Starting weights | Training on our data? | What question it answers |
|---|---|---|---|
| **P1 — Baseline** | the authors' released `karmadock_screening.pkl` | no (inference only) | how good is KarmaDock "out of the box"? |
| **P2 — From scratch** | random | yes, full 2-stage paper protocol | how good is it when trained *only* on the seminar data (the strict "standardized" reading)? |
| **P3 — Fine-tune** | released checkpoint | yes, continue training | does adapting the pretrained model to our split beat both? |

P1 is the reference point. P2 is the honest "retrain from nothing" number. P3 is the
practical "best of both worlds" attempt. Comparing the three tells us how much of
KarmaDock's skill is in the *architecture* vs in the *original training data*.

---

## 2. How KarmaDock works (the short version)

KarmaDock is a three-stage deep model (from the paper, *Nat. Comput. Sci.* 2023):

1. **Encoders** — a graph transformer (GT) encodes the protein pocket and a set of
   geometric vector perceptrons (GVP) encode the ligand. These turn atoms into feature
   vectors that know about local chemistry.
2. **EGNN docking module** — an E(n)-equivariant graph neural network with self-attention
   takes the rdkit starting pose of the ligand and *moves the atoms* to predict the bound
   pose. It does this with a "recycling" trick (3 recycles × 8 EGNN layers) so it can
   refine the pose repeatedly, similar to AlphaFold2. Equivariance means if you rotate the
   protein, the predicted pose rotates the same way — the network doesn't have to memorise
   orientations.
3. **MDN scoring** — a mixture density network looks at protein–ligand atom-pair distances
   and outputs a score for how strongly they bind. This score is what we use to rank poses.

After the EGNN predicts a pose, there's optional **post-processing** to make the structure
chemically sane: a force-field cleanup (**FF-corrected**) and an rdkit-conformer
alignment (**align-corrected**). The paper reports all three variants (raw / FF / aligned).
Our inference exports the corrected pose and keeps the raw/FF/aligned RMSDs for analysis.

The key thing I had to understand for training: the model's `forward(data, device,
pos_r)` returns `(rmsd_loss, mdn_loss)`, and **`pos_r` is a switch**. If `pos_r == 0`,
the forward *skips the whole EGNN docking part* and only computes the MDN scoring loss.
If `pos_r > 0`, it runs the EGNN and adds the pose RMSD loss. That single switch is what
lets us reproduce the paper's two-stage training without touching the model code.

---

## 3. The training protocol (straight from the paper) and how we implement it

The paper's "Training protocol" (Methods, p.801) trains in **two stages**:

**Stage 1 — scoring first.** Train just the MDN scoring block on the ground-truth poses.
Loss is `L = L_MDN + 0.001·L_atom + 0.001·L_bond` (the two aux terms are auxiliary
atom/bond-type classification tasks). Optimizer Adam, **batch 64, lr 1e-3, weight decay
1e-5**, stop when the validation loss hasn't improved for **70 epochs**.

**Stage 2 — docking + scoring together.** Now turn on the EGNN docking module and train it
*together with* the already-trained scoring module, starting from Stage 1's weights. Add
the docking loss (the RMSD between predicted and true pose) with **weight 1**. Same
settings **except lr 1e-4 and weight decay 0**.

Split: train/validation chosen randomly with **seed 42**.

How our code maps onto this (no changes to upstream KarmaDock — only our `train.py`
orchestrates it):

- **Stage 1** = `train.py --pos_r 0 --lr 1e-3 --weight_decay 1e-5 --patience 70 --random_seed 42`
- **Stage 2** = `train.py --pos_r 1 --lr 1e-4 --weight_decay 0 --patience 70 --random_seed 42 --init_model <stage1 best>`

`scripts/run_train_paper.sh` runs both stages in order and is what Pipeline 2 uses.

**Honest deviations (documented on purpose):**
- *Batch size.* The paper used 8×A100-80GB and a batch of 64. Our cluster GPUs are
  P100/V100 **16 GB**, where a batch of 64 doesn't fit. So we use a small physical batch
  with **gradient accumulation** (`--batch_size 4 --accum_steps 16 = effective 64`). The
  gradients are mathematically the same as batch 64, it's just slower. This is the one
  change I made to `train.py`.
- *Aux losses.* In the released code the `0.001·L_atom/L_bond` terms are computed but
  dropped by a line-break/operator-precedence quirk, so in practice Stage-1 optimises the
  MDN loss alone. The weight is tiny (0.001), so the effect is negligible, and I left the
  public code untouched for reproducibility. Worth knowing it's there.
- *Patience for fine-tuning (P3).* I use patience 30 instead of 70, because fine-tuning a
  pretrained model on a small set converges fast and a long patience just risks
  overfitting the prototype split.

---

## 4. The data

`prototype_model_data` (a zip the tutors gave us) contains:
- `proto_train.csv` / `proto_test.csv` — the official complex lists. Columns we use:
  `ligand_file_name`, `protein_file_name`.
- `proto_train/` and `proto_test/` — the actual structures: for each complex a
  `<id>_ligand_refined.sdf` (the crystal ligand) and `<id>_protein_refined.pdb` (the
  protein). There's also a rich `metadata.csv` inside each folder (affinities, SMILES,
  etc.) that we don't need for docking.

The complex **id** is just the ligand filename with `_ligand_refined.sdf` stripped, e.g.
`3ix2_AC2_A_302`. That id is the thread that ties everything together: the folder name,
the `.dgl` graph name, and the predicted-pose filename all use it.

**Data gap in `proto_test` (important).** `proto_test.csv` lists 118 complexes, but the
provided `proto_test/` folder only physically contains the structures for **75** of them —
43 (e.g. `5oai`, `5ove`, `5ovf`) are missing entirely. This is verified to be the dataset
as given (the local copy has the identical gap; it's not a naming mismatch or a bad unzip).
The folder also contains 61 `sdf` files that the CSV does *not* list, so the CSV and the
folder are out of sync both ways. We therefore benchmark on the **75 available** test
complexes and have flagged the missing 43 for the tutors. `proto_train` is complete (712).

---

## 5. The Docker image (`ahlamloum/karmadock-seminar:v3`)

The cluster only runs jobs in the **HTCondor docker universe**, so all our code lives in a
Docker image. Design choices:

- **Base:** `continuumio/miniconda3`. On top of it we clone the upstream KarmaDock repo to
  `/app/KarmaDock` and add our own scripts to `/app/scripts`.
- **The conda environment is the authors' own pre-packed `conda-pack` tarball**
  (`karmadock_env.tar.gz`, ~3.3 GB from Zenodo), not `conda env create`. Reason: running
  conda's dependency solver was getting OOM-killed (especially under emulation). The pack
  is just download → extract → `conda-unpack`, no solving, and it's exactly the env the
  authors used (torch 1.12.1, rdkit 2022.09, torch_geometric, MDAnalysis, prody, …).
- `python3` resolves to that env, and `PYTHONPATH=/app/KarmaDock`, so any script can
  `import` KarmaDock modules and Condor can run our shell scripts with no activation step.
- Built **natively on linux/amd64** so it matches the cluster (no QEMU). `:v3` adds the
  two-stage training scripts + gradient accumulation on top of `:v2`.

Why the image matters for the cluster: because the code is *inside the image*, the Condor
submit files don't need to transfer any code (a previous attempt broke exactly there — a
trailing slash flattened the `scripts/` dir and Python couldn't find the files). We only
keep **data and outputs** on the shared `/home`, which Condor mounts into the container.

---

## 6. The scripts, one by one

All live in `scripts/`. Shell scripts are thin wrappers; the real logic is in the Python.

### `convert_seminar_to_karmadock.py`
Seminar layout → KarmaDock layout. Reads the CSV, and for each row copies
`<id>_ligand_refined.sdf` → `<out>/<id>/<id>_ligand.sdf` and the protein likewise. That
per-complex folder layout is what KarmaDock's preprocessing expects.

### `preprocess.sh`  →  KarmaDock `pre_processing.py` + `generate_graph.py`
Turns raw structures into model-ready graphs, in three steps:
1. convert (above);
2. `pre_processing.py` — cuts a **12 Å pocket** around the crystal ligand using prody (no
   Schrödinger needed);
3. `generate_graph.py` — builds one `<id>.dgl` graph file per complex. (The `.dgl`
   extension is just a filename — KarmaDock saves with torch/pickle, it does **not** use
   the DGL library.) Each graph stores the crystal pose as the target (`ligand.xyz`) and a
   fresh rdkit pose as the start (`ligand.pos`), re-randomised every epoch.

Output: a folder of `.dgl` graphs. This is shared by every pipeline.

### `train.py`  (our main new artifact)
A proper checkpointed training loop wrapped around KarmaDock's own `forward`. Highlights:
- builds train/val split deterministically from the CSV (`--random_seed`, paper uses 42),
  skipping any complex whose graph failed to build;
- `loss = pos_r·rmsd_loss + mdn_loss`, i.e. `pos_r` picks the training stage;
- **gradient accumulation** (`--accum_steps`) for effective batch 64 on a 16 GB GPU;
- validates each epoch with KarmaDock's own `karmadock_evaluation`;
- saves the best checkpoint (`karmadock_team002.pkl`, lowest val loss, via the upstream
  `Early_stopper`) **and** a `last.pt` every epoch so the job can `--resume` after a
  cluster reschedule;
- writes `train_log.csv` (per-epoch train/val rmsd & mdn losses) — this is what the
  results notebook plots;
- optional Weights & Biases logging (only if `WANDB_API_KEY` is set; otherwise it's a
  no-op and we still get `train_log.csv`).

### `run_train_paper.sh`  (Pipeline 2)
Runs the two paper stages in order (Stage 1 `pos_r 0`, then Stage 2 `pos_r 1` initialised
from Stage 1), each in its own sub-folder, both reschedule-safe. A `stage.done` sentinel
stops Stage 1 from re-running once it's finished if the whole job restarts.

### `run_finetune.sh`  (Pipeline 3)
A single fine-tuning run: `--init_model karmadock_screening.pkl --pos_r 1 --lr 1e-4
--weight_decay 0 --patience 30`. Same effective batch and seed as P2.

### `run_infer.sh`  →  KarmaDock `ligand_docking.py` + `convert_karmadock_to_seminar.py`
Inference, used by all three pipelines (only the `--model_file` differs):
1. `ligand_docking.py` docks + scores + applies FF/align correction, writing per-repeat
   `<re>.csv` (pdb_id, score, RMSD, FF_RMSD, Aligned_RMSD) and the pose SDFs;
2. `convert_karmadock_to_seminar.py` collects the poses into one ranked
   `<id>_pred.sdf` per complex (best MDN score first), which is exactly the format the
   tutors' evaluator wants.

### `cluster_smoke.sh` / `collect_cluster_logs.sh`
Helpers (not part of the science): a one-shot environment check, and a log aggregator
that dumps condor status + every job's full stderr into one `~/run/logs/CONSOLIDATED.log`.

---

## 7. The cluster: how the scripts actually run

The HPC is the Saarland **SIC** cluster (login `conduit.hpc.uni-saarland.de`), scheduler
**HTCondor**, and we run in the **docker universe** (the only kind allowed).

Mental model:
- We `ssh` to a **login/submit node** (no GPUs there). We never compute on it; we just
  `condor_submit` jobs.
- HTCondor matches each job to a **worker node** with the requested resources (e.g. 1 GPU),
  pulls our Docker image there, and runs our `executable` inside the container **as our
  user**.
- `/home` is a shared NFS filesystem. We add `+WantGPUHomeMounted = true` so the worker
  mounts `/home` into the container. That's how the container at
  `/home/bdldt_team002/run/...` sees the same files we see on the login node — **no file
  transfer needed**. `requirements = UidDomain == "cs.uni-saarland.de"` keeps the job on
  nodes where our user/home is valid.
- Because the `executable` is an **absolute** path (e.g. `/app/scripts/preprocess.sh`),
  Condor treats it as a path *inside the container* (our baked-in script). Data paths in
  the `arguments` are absolute `/home/...` paths, visible thanks to the home mount.

### Directory layout on the cluster (`~/run/`)
```
run/
├── code/                # this repo, rsync'd up (scripts, condor/, docs, notebook)
├── data/proto/          # unzipped prototype data (proto_train.csv, proto_train/, proto_test*…)
├── work/
│   ├── complex/{proto_train,proto_test}    # KarmaDock-layout complexes (intermediate)
│   ├── graphs/{proto_train,proto_test}     # the .dgl graphs
│   ├── ckpt/p2_scratch/{stage1_scoring,stage2_docking}   # P2 checkpoints
│   ├── ckpt/p3_finetune/                   # P3 checkpoint
│   └── kd_out/{p1_baseline,p2_scratch,p3_finetune}/proto_test   # raw KarmaDock output
├── results/{p1_baseline,p2_scratch,p3_finetune}/proto_test      # final <id>_pred.sdf
└── logs/                # condor .out/.err/.log + RUN_TRACKER.log + CONSOLIDATED.log
```

### The submit files (`condor/`) and the order to run them
1. `preprocess_train.sub`, `preprocess_test.sub` — CPU jobs, build the graphs (shared).
2. `p1_infer_baseline.sub` — GPU, Pipeline 1 (needs test graphs only).
3. `p2_train_scratch.sub` — GPU, Pipeline 2 training (needs train graphs). Long-running.
4. `p3_finetune.sub` — GPU, Pipeline 3 training (needs train graphs).
5. `p2_infer.sub`, `p3_infer.sub` — GPU, dock proto_test with each trained checkpoint.

Each `.sub` writes its own `.out` (stdout), `.err` (stderr — where errors land), and
`.log` (Condor events) into `~/run/logs/`.

### `should_transfer_files = NO` + the shared mount (how files reach the job)
HTCondor jobs run on a remote *execute* node that may not share a filesystem with the submit
node. `should_transfer_files` decides how the job gets its input/output:
- **`YES`** — Condor ships `transfer_input_files` to a scratch dir on the execute node, runs there,
  copies outputs back (needed when there is *no* shared filesystem).
- **`NO`** (what we use) — Condor copies **nothing**; the job assumes a **shared filesystem** is
  already mounted at the same absolute paths on the execute node and reads/writes directly there.
- `IF_NEEDED` — auto-decides based on whether submit/execute share a filesystem.

We use **`NO`** because the cluster has a **shared NFS `/home`** on every node, and
**`+WantGPUHomeMounted = true`** bind-mounts `/home` *into the Docker container* as well. So all
data/code/outputs under `/home/bdldt_team002/run/…` are visible at the **same path** on whatever
node grabs the job — which is why every sub's `arguments` use absolute `/home/...` paths and none
list `transfer_input_files`. Upside: the 80 MB+ datasets, GBs of `.dgl` graphs, and checkpoints are
used **in place** (no per-run copying), and outputs land straight in `~/run/results` / `~/run/work`.
This also avoids the earlier `transfer_input_files = scripts/` bug (the trailing slash flattened
files into scratch and broke paths — see `RUN_JOURNAL.md`).

### Reproducing from scratch (the whole thing, in order)
```bash
# 0. (one time) build + push the image, native amd64
docker build -t <user>/karmadock-seminar:v3 -f docker/Dockerfile .
docker push <user>/karmadock-seminar:v3

# 1. on the cluster: put data + code in place
#    unzip prototype_model_data.zip -> ~/run/data/proto/
#    rsync this repo -> ~/run/code/

# 2. submit, in order (wait for each stage's graphs/checkpoints to exist first)
cd ~/run/code/condor
condor_submit preprocess_train.sub
condor_submit preprocess_test.sub
condor_submit p1_infer_baseline.sub
condor_submit p2_train_scratch.sub
condor_submit p3_finetune.sub
# after training finishes:
condor_submit p2_infer.sub
condor_submit p3_infer.sub

# 3. watch progress / collect all errors into one file
bash ~/run/code/scripts/collect_cluster_logs.sh   # -> ~/run/logs/CONSOLIDATED.log
```

---

## 8. Logging & tracking the run

Two layers:
- **`~/run/logs/RUN_TRACKER.log`** — an append-only timeline (timestamp + event) of every
  submission and milestone, so there's a single story of what happened when.
- **`~/run/logs/CONSOLIDATED.log`** — produced by `collect_cluster_logs.sh`: a one-shot
  snapshot of `condor_q`/`condor_history`, any hold reasons, which artifacts exist so far,
  the tail of each `train_log.csv`, and the **full stderr of every job**. This is the first
  place to look when something breaks.

---

## 9. Results & comparison

See **`notebooks/results_and_comparison.ipynb`** (run on the cluster, or anywhere the
`run/` tree is synced — set `KD_BASE`). It produces, for P1 vs P2 vs P3:
- the metrics table (mean/median RMSD, success @2 Å and @1 Å, per pose variant);
- the **cumulative RMSD success curve** (ECDF), matching the paper's Fig. 2a,b;
- **docking speed** (s/pose, parsed from `ligand_docking.py`'s `Time Spend`), matching the
  paper's Fig. 2c,d — the paper's reference is ~0.017 s/pose on a V100. Speed is part of the
  cross-tool comparison the tutors run, so we report KarmaDock's number explicitly;
- training curves for P2 (both stages) and P3;
- top-pose visualization (predicted vs crystal, with an optional 3D overlay).

### Prototype results (2026-06-13, best-of-3 on the 75 available `proto_test` complexes)

| pipeline | success @2 Å | success @1 Å | median RMSD | docking speed |
|---|---|---|---|---|
| **P1 baseline** (released weights) | **56.0%** | 9.3% | 1.90 Å | ~1.87 s/pose |
| **P3 fine-tune** (released → trained on 712) | **29.3%** | 9.3% | 2.13 Å | ~1.87 s/pose |
| **P2 from-scratch** (random → trained on 712) | **4.0%** | 0.0% | 5.96 Å | ~1.88 s/pose |

(All success rates are *uncorrected* — the best variant here. Numbers via
`notebooks/results_and_comparison.ipynb`, which also draws the ECDF curves, training curves,
and pose overlays.)

**Headline finding:** on this tiny prototype set, **retraining HURTS vs the released model**
(baseline > fine-tune > from-scratch). Fine-tuning on ~640 complexes overfits the small
in-distribution split (good val RMSD ~2.6 Å) and loses the baseline's generalization to
`proto_test`; from-scratch can't learn docking from so little data. This validates the
pipeline end-to-end and shows the result is *training-data-limited* — the real comparison
needs the full dataset (and ideally LP-PDBBind's leak-proof split + the warmup idea in the
journal). Verified not a bug: same inference path as P1, and all three checkpoints load and
give distinct numbers.

**Correction trade-off:** FF/align correction *reduces* accuracy here (P1 56→34.7→10.7%,
P3 29.3→26.7→16.0%, P2 flat at 4%), opposite to the paper on PDBBind core — so we submit the
**uncorrected** poses (PoseBusters validity may still favour corrected; accuracy-vs-validity
trade-off to note).

**Speed** ≈ 1.87 s/pose on a P100, ~identical across pipelines (same architecture); paper
reports 0.017 s/pose on a batched V100. Reported for the cross-tool comparison.

**PoseBusters physical validity (top pose, redock mode, on the align-corrected `_pred.sdf`):**

| pipeline | PB-Valid % | rmsd≤2Å % (PB, symmetry-corrected) |
|---|---|---|
| P1 baseline | 13.3% | 44.0% |
| P3 fine-tune | 6.7% | 29.3% |
| P2 from-scratch | 0.0% | 4.0% |

PB-Valid is **low across the board**, dominated by **protein clashes**
(`minimum_distance_to_protein` fails 83–97% of poses), plus high `internal_energy` and
`volume_overlap_with_protein`. This is the classic PoseBusters finding — DL docking yields
physically-implausible poses even at reasonable RMSD; KarmaDock's accuracy doesn't come with
validity. **Metric caveat:** PoseBusters' *symmetry-corrected* RMSD is much more lenient than
KarmaDock's internal `Aligned_RMSD` (PB: 44% of P1 align poses ≤2 Å vs KarmaDock's 10.7%
best-of-3), so the official tutor RMSD (also symmetry-corrected, via their `evaluation.py`) may
be higher than our KarmaDock-internal numbers. Run their script for the authoritative figures.

---

## 10. Known issues / things to watch

- **W&B key** was hardcoded in the older `run_train.sh`; the new wrappers read it from the
  environment instead. If this repo ever goes public, rotate that key.
- **Worker internet for W&B** is uncertain, so the cluster runs default to *no* W&B
  (we still get `train_log.csv`). To enable it, set `WANDB_MODE=offline` in the submit
  file's `environment` and `wandb sync` afterwards.
- **GPU memory (16 GB).** If a training job goes on *hold* with a memory error, lower
  `--batch_size` (and raise `--accum_steps` to keep the effective batch at 64).
- **From-scratch on prototype data is expected to underperform** the pretrained model —
  712 complexes is tiny. That's fine: the prototype is about proving the pipeline; the
  real numbers come with the full dataset.

---

## 11. Pipelines P4 & P5 — LP-PDBBind leak-proof benchmark

**Goal.** An *honest generalization* number: train/evaluate KarmaDock on the **Leak-Proof
PDBBind (LP-PDBBind)** split (Li et al., *J. Phys. Chem. B* 2026), whose train/val/test are
built so that train↔test max protein-sequence similarity ≤ 0.5 and ligand similarity ≤ 0.99
(and val is made as dissimilar from train as test is). This removes the train/test leakage that
inflates the classic PDBBind core-set numbers.

- **P4 = LP fine-tune** — fine-tune the released `karmadock_screening.pkl` on LP-train (single GPU).
- **P5 = LP from-scratch** — paper 2-stage protocol from random init on LP-train, **multi-GPU**.

### 11.1 The split and clean levels (what we use)
LP-PDBBind ships a finished metadata table `dataset/LP_PDBBind.csv` (19,443 rows). We **consume
it directly** — we do NOT re-run the `dataset_creation/` notebooks (those rebuild the split from
raw PDBBind + a hardcoded author path and need the licensed structures already on disk; their
only network step downloads RCSB *headers*, i.e. metadata, not structures).

- Split column `new_split`: **train 11,513 / val 2,422 / test 4,860** (+648 discarded as
  too-similar).
- Clean-level boolean columns, nested CL3 ⊂ CL2 ⊂ CL1; plus a `covalent` flag.
- **Protocol (paper default, what we adopt): train+val on CL1, test on CL2, noncovalent only**
  ("All of the results reported here were based on training on CL1 data and testing on CL2.").
  Trainable noncovalent counts: train CL1 ≈ 7,393, val CL1 ≈ 1,891, test CL2 ≈ 2,171.
- Evaluation: KarmaDock is a *pose* tool, so we do **not** use LP's affinity `evaluation.py`;
  we reuse our own success@2 Å RMSD pipeline on the LP test split (and, license-free, on the
  in-repo **BDB2020+** external set: 136 complexes with structures bundled in the repo).

### 11.2 PDBBind v2020 structures (the one external dependency)
The CSV is metadata only; KarmaDock needs the actual `*_protein.pdb` / `*_ligand.sdf`. These
come from the official PDBBind v2020 archives (downloadable without subscription; see
`../LP-PDBbind-journal.md` for the URLs that work). We download + extract them **directly on the
cluster** (gigabit link, 16 TB free on `/home`) rather than uploading from a laptop:

```
~/run/data/pdbbind/archives/    PDBbind_v2020_{plain_text_index,other_PL,refined}.tar.gz
~/run/data/pdbbind/extracted/   v2020-other-PL/<id>/...  refined-set/<id>/...
```
Each `<id>/` holds `<id>_protein.pdb`, `<id>_pocket.pdb`, `<id>_ligand.sdf`, `<id>_ligand.mol2`.
All three archives pass `gzip -t`. (The `plain_text_index` archive is only needed to *derive*
the CL2 flag from raw PDBBind; we already have CL2 in the CSV, so it is not on the critical path.)

### 11.3 New scripts
- **`scripts/lp_to_seminar.py`** — the only new data code. Reads `LP_PDBBind.csv`
  (PDB id = unnamed index col), filters by `new_split` + clean level + non-covalent, locates each
  id under the extracted PDBBind tree (`v2020-other-PL/` or `refined-set/`, with a glob fallback),
  and emits seminar-format `lp_{train,val,test}.csv` + `lp_{train,val,test}/<id>_ligand_refined.sdf`
  / `_protein_refined.pdb` (symlinks by default; `--copy` to copy) plus `lp_manifest.json`
  recording every dropped id (missing structure or `.mol2`-only). Flags:
  `--train_clean CL1 --test_clean CL2` (paper default), `--keep_covalent`, `--copy`.
- **`scripts/train.py`** — gained two capabilities (single-GPU path byte-for-byte unchanged, so
  P2/P3 stay reproducible):
  - **`--val_csv` / `--val_graph_dir`**: use an *explicit* validation split (LP's leak-proof val),
    instead of the random `--val_frac` carve-out. Train then uses all of `--csv`.
  - **Multi-GPU (DDP)**: opt-in, activated only under `torchrun` (WORLD_SIZE>1). Data are sharded
    by striping the complex-id list per rank (needs no sampler support from KarmaDock's custom
    `PassNoneDataLoader`); DDP all-reduces gradients, we additionally all-reduce the scalar
    metrics so every rank makes the identical early-stop decision; only rank 0 writes
    checkpoints/logs/W&B. `find_unused_parameters=True` because stage-1 scoring (`pos_r=0`) skips
    the EGNN docking branch. `no_sync()` skips the gradient all-reduce on non-boundary
    accumulation micro-steps. Both DataParallel and DDP store params under `module.`, so the
    checkpoint format is identical to P2/P3 and inference is unchanged.
- **`scripts/run_finetune.sh`** — P4 reuses it; optional args 7/8 = `<val_csv> <val_graph_dir>`
  (sets the W&B run name to `p4_lp_finetune` when a val CSV is given).
- **`scripts/run_train_lp_scratch.sh`** (new) — P5. Same two-stage paper protocol as
  `run_train_paper.sh`, but auto-detects the GPU count (`nvidia-smi -L`) and launches via
  `torchrun --nproc_per_node=$NGPU` when >1 (else plain `python3`). Uses `--val_csv`/`--val_graph_dir`.

### 11.4 New condor subs (`condor/`)
All reference image **`:v5`** (= v4 + the updated `train.py`/wrappers + `lp_to_seminar.py`; must
be built+pushed before submitting — task 14) and keep the `idun`-excluded requirements.
- `preprocess_lp_{train,val,test}.sub` — CPU, reuse `preprocess.sh` → `run/work/graphs/lp_*`.
- `p4_lp_finetune.sub` — 1 GPU; args pass `lp_val.csv` + `graphs/lp_val` for explicit validation.
- `p5_lp_scratch.sub` — `request_gpus=4`, per-rank batch 4 × accum 4 → effective batch 64 (= paper)
  across 4 GPUs; wrapper adapts if fewer are allocated. **Smoke-test the DDP path (2 GPUs, a few
  epochs) before the full run** — the DDP code has not yet run on real GPUs.
- `p4_lp_infer.sub` / `p5_lp_infer.sub` — 1 GPU; dock `lp_test`, export poses (re-export
  `--mode uncorrected` if those are the submitted poses, as on proto_test).

### 11.5 Run order
```
# (once) build+push image v5 with the new scripts
# on the cluster:
python3 ~/run/code/scripts/lp_to_seminar.py \
    --lp_csv .../LP-PDBBind/dataset/LP_PDBBind.csv \
    --pdbbind_dir ~/run/data/pdbbind/extracted --out_dir ~/run/data/lp
condor_submit preprocess_lp_train.sub ; preprocess_lp_val.sub ; preprocess_lp_test.sub
condor_submit -a 'environment = "WANDB_API_KEY=<key>"' p4_lp_finetune.sub   # P4
# smoke-test DDP, then:
condor_submit -a 'environment = "WANDB_API_KEY=<key>"' p5_lp_scratch.sub    # P5
condor_submit p4_lp_infer.sub ; p5_lp_infer.sub        # after each checkpoint exists
# add 'P4 LP-finetune':'p4_lp' and 'P5 LP-scratch':'p5_lp' to the notebook PIPES/INFER_LOG dicts
```

### 11.6 Workaround — run preprocessing locally via Docker when the cluster CPU queue is jammed

Preprocessing (`preprocess.sh` → `pre_processing.py` + `generate_graph.py`) is **CPU-only and
needs no GPU**, so it can run on any machine that has the project image — handy when the cluster's
CPU slots are contended and a `preprocess_*` job sits idle in the queue. Inference still wants the
cluster GPU, so the pattern is: **preprocess locally → ship the `.dgl` graphs to the cluster → run
GPU inference there**. (Only the graphs are needed for inference, not the `complex/` dir.)

```bash
# 1) materialise the seminar-format inputs locally (stdlib adapter; --copy so files are real)
python3 scripts/bdb_to_seminar.py --bdb_root <extracted_BDB2020+> --out_dir bdb_local --copy

# 2) preprocess inside the image (CPU); docker writes as root
sudo docker run --rm -v "$PWD/bdb_local:/data" ahlamloum/karmadock-seminar:v6 \
    bash /app/scripts/preprocess.sh /data/bdb2020.csv /data/bdb2020 \
         /data/complex/bdb2020 /data/graphs/bdb2020
sudo chown -R "$USER" bdb_local            # graphs come out root-owned

# 3) ship graphs to the cluster, drop the redundant cluster preprocess, let inference run there
rsync -az bdb_local/graphs/bdb2020/ <cluster>:~/run/work/graphs/bdb2020/
# condor_rm <preprocess_job> ; then submit p1_bdb_infer.sub / p4_bdb_infer.sub
```

Used on 2026-06-14 for BDB2020+ (135/136 graphs) when `preprocess_bdb` would not schedule even at
2 CPUs. The same recipe works for any split (swap the adapter/paths). Note the local machine has no
GPU, so only the CPU preprocessing is offloaded; training/inference stay on the cluster.
