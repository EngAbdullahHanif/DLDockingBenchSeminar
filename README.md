# KarmaDock — BDLDT seminar · review copy [Abdullah]

### This is not a final submission repo. It's for review only. 
Hey Abdullah — this is new try for KarmaDock prototype work, shared so you can **understand what we
did, review it, and send back comments** before we finalize the 19 Jun submission. Read this
page, skim the code/notebook, and reply to the **"What I need from you"** section at the bottom.

**Please try to read this document - Don't skip** 

> (code line-by-line + theory, with a dark/light toggle): open
> **`KARMADOCK_EXPLAINED.html`** in any browser.

---

## 1. What the project is
The seminar *"Benchmarking DL-based Docking Tools"* (Saarland Uni) gives each team one
deep-learning **docking** tool. Ours is **KarmaDock**. Docking = given a protein pocket and a
small molecule (ligand), predict the ligand's 3D binding **pose**. We retrain KarmaDock on the
seminar's shared split and compare it against the released model.

## 2. What is KarmaDock?
A deep-learning docking method. It builds graphs for the protein and the ligand, encodes them
(GVP + graph-transformer blocks), **moves the ligand into the pocket** with an E(n)-equivariant
GNN (EGNN, recycled ×3), and **scores** the pose with a mixture-density network (MDN). It
generates the pose directly instead of searching, so it is ~100–1000× faster than classical
docking. Paper: Zhang et al., *Nat. Comput. Sci.* 3, 789–804 (2023),
[doi:10.1038/s43588-023-00511-5](https://doi.org/10.1038/s43588-023-00511-5).

## 3. The one thing that makes our work "ours"
Public KarmaDock ships **inference + released weights only — no training script**. So our
contribution is **`scripts/train.py`** (a full checkpointed 2-stage training loop), the
seminar↔KarmaDock **data adapters**, the **run wrappers**, and the whole **HTCondor**
orchestration on the SIC cluster. We call the upstream model/preprocessing/docking
**unmodified**. The exact ours-vs-upstream split is in **`PROVENANCE.md`**.

## 4. Three pipelines, one comparison
| pipeline | what it is | checkpoint |
|---|---|---|
| **P1 baseline** | released `karmadock_screening.pkl`, inference only | upstream weights |
| **P2 from-scratch** | paper's 2-stage protocol, trained on proto_train | `p2_scratch_*.pkl` |
| **P3 fine-tune** | released weights fine-tuned on proto_train | `p3_finetune_*.pkl` |

**Result** (success@2Å, best-of-3, on the 75 available proto_test complexes — from
`notebooks/results_and_comparison.ipynb`):

| pipeline | uncorrected | FF | align |
|---|---|---|---|
| P1 baseline | **56.0%** | 34.7% | 10.7% |
| P3 fine-tune | **29.3%** | 26.7% | 16.0% |
| P2 from-scratch | **4.0%** | 4.0% | 4.0% |

**PoseBusters PB-Valid** (notebook §3e): P1 13.3% / P3 6.7% / P2 0%.

**Headline finding (honest):** on this tiny prototype set, retraining *hurts* vs the released
baseline — small-data overfit/forgetting. The pipeline works end-to-end; matching the paper
needs the full dataset. This is the expected prototype outcome, not a bug.

## 5. Repo layout
```
scripts/      our code: train.py (main artifact), converters, preprocess.sh, run_*.sh
condor/       HTCondor submit files (preprocess, p1/p2/p3)
docs/         DOCUMENTATION.md, RUNBOOK.md, RUN_COMMANDS.md
notebooks/    results_and_comparison.ipynb  (tables, ECDF, PoseBusters, pose views)
eda/          data_exploration.ipynb + figures
results/      predicted poses, 75 per pipeline (uncorrected + FF), best-pose-first
data/         proto_train.csv / proto_test.csv  (the 80 MB zip is NOT shipped here)
cluster_artifacts/  file-name manifests of the cluster run (graphs 712+75, kd_out 678/pipe)
Dockerfile    image recipe (prototype image = ahlamloum/karmadock-seminar:v4)
PROVENANCE.md what we wrote vs upstream KarmaDock
KARMADOCK_EXPLAINED.html   the full guided walkthrough
ISSUES.md     short list of the bugs/issues we hit and fixed
```
**Not included on purpose:** training checkpoints (`*.pkl`), the dataset zip, the vendored
`KarmaDock/` upstream copy, the PDFs, and our full dev journal (see `ISSUES.md` for the short
version). No secrets, no W&B key — W&B is read from an env var only.

## 6. Where to look (priority order)
1. `PROVENANCE.md` — what's ours vs upstream. **Confirm you're happy defending this split.**
2. `scripts/train.py` — our main artifact. The part most worth your scrutiny **[IMPORTANT]**.
3. `notebooks/results_and_comparison.ipynb` — all numbers in §4 come from here.
4. `docs/RUNBOOK.md` — the exact cluster run steps - _not updated_.
5. `KARMADOCK_EXPLAINED.html` — if you want the gentle, full explanation first.

## 7. Experimental — P4 & P5 (LP-PDBBind) · NOT part of the prototype

> Heads-up: **P4 and P5 are experimental**, built for the **full-data / final submission** (and
> to study data leakage). They are **not** part of the 19 Jun prototype, and none of their code
> or checkpoints are shipped in this repo — this section is just so you know they exist.

Same KarmaDock pipeline, but trained/evaluated on **LP-PDBBind** — a *leak-proof* re-split of
PDBBind 2020 that separates train/test by protein + ligand similarity (paper protocol: train+val
on clean-level **CL1**, test on **CL2**, non-covalent). Selected counts: train 7,393 / val 1,891 /
test 2,171 (after RDKit drops ~14% on the as-given ligand SDFs: 6,377 / 1,552 / 1,862 graphs).

| pipeline | what it is |
|---|---|
| **P4 — LP fine-tune** | released weights fine-tuned on LP CL1 train (1 GPU) |
| **P5 — LP from-scratch** | 2-stage from scratch on LP CL1 train (DDP multi-GPU; pivoted to single-GPU on the cluster) **running now** :(> ~2 days) |

**Why they exist (data leakage):** `lp_test` is all PDBBind v2020 — exactly what the *released*
weights were trained on. So for any released-weights model (P1, **P4**), `lp_test` is **leaked**:
P4 scores 94.5% success@2Å there, which is memorization, **not** generalization. `lp_test` is a
valid leak-proof test **only for P5** (trained from scratch, never saw it). For released-weights
models the honest external test is **BDB2020+** (BindingDB, post-2020 → unseen).

**What we found so far** (numbers from `RUN_JOURNAL.md`, not yet in the shipped notebook):
- **Honest external (BDB2020+):** P1 44.4% vs **P4 40.0%** success@2Å — fine-tuning did **not**
  help; P4's best checkpoint ≈ the released weights.
- **On the tutor's proto_test:** **P4 54.7%** vs P1 56.0 / P3 29.3 / P2 4.0. Key result —
  fine-tuning on the larger/cleaner LP CL1 (~6.4k) *preserves* the baseline, whereas the tiny
  proto fine-tune (P3) *degraded* it ⇒ P3's drop was a **small-data artifact**, not a method flaw.
- **P5** (the one genuinely-valid leak-proof number) is **still training** — no final figure yet.

Code for these lives in the main working repo (not here): `scripts/lp_to_seminar.py`,
`scripts/run_train_lp_scratch.sh`, `scripts/bdb_to_seminar.py`, and the `condor/p4_*` / `p5_*` subs.

---

## What I need from you (Abdullah)

### A. Sanity-check these 
- **train.py 2-stage logic** — Stage 1 scoring (`pos_r 0`) → Stage 2 docking (`pos_r 1`),
  seed 42, effective batch 64 via grad-accumulation. Does it match the paper's protocol [method section]?
- **P3 number** — journal/early notes say "~24%", finalized notebook says **29.3%**. Confirm
  29.3% is what we report everywhere _[ confirm the results is consistens - mostly ai hardcoded information mistakes ]_.
- **Data gap** — `proto_test.csv` lists 118 complexes but only **75** have structures; we
  benchmark on 75 and raise the missing 43 at office hours. OK to state it that way or should we the unlisted 61 complex to the csv file and run the   test again?
- **Docs** — `PROVENANCE.md`/`REVIEW_NOTES.md` mention `papers/KarmaDock_paper.md` - how do you recommend to document our work?.

### B. Open decisions — need your call
1. Anything **missing** for the 19 Jun deliverable (code / checkpoint / notebook / poses ZIP / Docker name / condor files)?

Send me your comments on A + B and I'll fold them in, then we finalize together before the deadline. Thanks!
