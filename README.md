# KarmaDock — BDLDT Seminar (Phase 2 Prototype)

This repository contains the Phase 2 prototype implementation and benchmarking results for **KarmaDock**, as part of the *"Benchmarking DL-based Docking Tools"* seminar at Saarland University.

> **Note on code walkthrough & theory:** Open **`KARMADOCK_EXPLAINED.html`** in a browser to see a detailed line-by-line code and theory guide.

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

**Result** — official evaluator (`evaluation/evaluation.py`, symmetry-corrected RMSD, **top-1**, on the **corrected 136-complex** proto_test; from `notebooks/results_and_comparison.ipynb`). _Updated 2026-06-16._

| pipeline | uncorrected (headline) | FF-corrected | <1 Å | median RMSD |
|---|---|---|---|---|
| **P1 baseline** (released weights) | **81.6%** | 79.4% | 8.1% | 1.45 Å |
| **P3 fine-tune** (released → trained on 712) | **80.9%** | - | 7.4% | 1.49 Å |
| **P2 from-scratch** (random → trained on 712) | **11.8%** | 9.6% | 3.7% | 3.00 Å |

> **`align_corrected` is excluded.** On this redocking set the align step reconstructs the crystal
> (reference) pose instead of following the model's prediction — a leak: even the weak P2 "scores"
> ~94%. Report **uncorrected**; **FF** is the paper's "most plausible" pose. **PoseBusters is deferred**
> to the next submission (per tutor).

**Headline finding:** the released model (P1) docks this fragment-heavy set well (81.6%). The from-scratch P2 model trained on only ~700 complexes achieves 11.8% success, showing the pipeline works end-to-end but requires the full dataset to generalize. The restored P3 fine-tune pipeline achieves a strong **80.9%** success, showing that fine-tuning on `proto_train` is stable and successfully preserves baseline generalization without catastrophic forgetting.

## 5. Repo layout
```
scripts/      our code: train.py (main artifact), converters, preprocess.sh, run_*.sh
condor/       HTCondor submit files (preprocess, p1/p2/p3)
docs/         DOCUMENTATION.md, RUNBOOK.md, RUN_COMMANDS.md
notebooks/    results_and_comparison.ipynb  (tables, ECDF, PoseBusters, pose views)
eda/          data_exploration.ipynb + figures
results/      predicted poses, 136 per pipeline (uncorrected + FF), best-pose-first
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
1. `PROVENANCE.md` — what's ours vs upstream.
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
| **P5 — LP from-scratch** | 2-stage from scratch on LP CL1 train (completed) |

**Why they exist (data leakage):** `lp_test` is all PDBBind v2020 — exactly what the *released*
weights were trained on. So for any released-weights model (P1, **P4**), `lp_test` is **leaked**:
P4 scores 94.5% success@2Å there, which is memorization, **not** generalization. `lp_test` is a
valid leak-proof test **only for P5** (trained from scratch, never saw it). For released-weights
models the honest external test is **BDB2020+** (BindingDB, post-2020 → unseen).

**What we found & finalized:**
- **P5 from-scratch results:** P5 converged on the training set (Train RMSD **3.05 Å**, Train Loss **4.24**), but suffered severe overfitting on the unseen validation split with a final Val RMSD of **7.48 Å** (Val Loss **8.76**). This highlights the limits of training a high-capacity GNN docking model on small datasets (~6.4k complexes) from scratch.
- **P4 Fine-tune & Leakage confirmation:** P4 showed a stable validation RMSD (**2.76 Å**) from epoch 0. However, this is due to pre-training leakage, as the released baseline weights (P1) were trained on the entire PDBBind v2020 dataset, which includes the LP validation complexes.
- **Honest external (BDB2020+):** P1 44.4% vs **P4 40.0%** success@2Å — fine-tuning did **not**
  help; P4's best checkpoint ≈ the released weights.
- **On the tutor's proto_test:** **P4 54.7%** vs P1 56.0 / P3 29.3 / P2 4.0. Key result —
  fine-tuning on the larger/cleaner LP CL1 (~6.4k) *preserves* the baseline, whereas the tiny
  proto fine-tune (P3) *degraded* it ⇒ P3's drop was a **small-data artifact**, not a method flaw.

Code for these lives in the main working repo (not here): `scripts/lp_to_seminar.py`,
`scripts/run_train_lp_scratch.sh`, `scripts/bdb_to_seminar.py`, and the `condor/p4_*` / `p5_*` subs.


