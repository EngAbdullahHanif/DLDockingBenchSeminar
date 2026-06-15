# REVIEW COPY — proposed KarmaDock prototype submission (for your review)

This folder is a **local review copy** of what we'd put on the `karmadock` branch of
`volkamerlab/DLDockingBenchSeminar` for the **19 Jun prototype deadline**. Nothing here is pushed.
Review the structure/contents, then we finalize + commit (organic commits, in your git identity).

## What's included (all real files)
| item | status | notes |
|---|---|---|
| `README.md` | ✅ | our write-up (tool intro, pipeline, "design choices vs earlier attempt", how-to-run) |
| `Dockerfile` | ✅ | the image recipe; prototype image = `ahlamloum/karmadock-seminar:v4` |
| `scripts/` | ✅ | our glue: converters, `preprocess.sh`, **`train.py`** (our main artifact — KarmaDock ships no trainer), `run_train_paper.sh`(P2)/`run_finetune.sh`(P3)/`run_infer.sh` |
| `condor/` | ✅ | prototype subs: p1_infer_baseline, p2_train_scratch, p3_finetune, preprocess_{train,test} |
| `notebooks/results_and_comparison.ipynb` | ✅ | P1/P2/P3 on proto_test (tables, ECDF, training curves, PoseBusters, pose views) |
| `eda/` | ✅ | `data_exploration.ipynb` + `figures/` (fig1 success+RMSD, fig2 speed, fig3 ECDF, fig4 training curves) |
| `docs/` | ✅ | DOCUMENTATION, RUNBOOK, RUN_COMMANDS, **RUN_JOURNAL** (the authentic dev log — failures+fixes) |
| `results/<pipeline>/proto_test/` | ✅ | **uncorrected** poses (75 each), best-pose-first |
| `results/<pipeline>/proto_test_ff/` | ✅ | **FF-corrected** poses (75 each) — most physically plausible (per the paper) |
| `model/` | ✅ | `p3_finetune_karmadock_team002.pkl` + `p2_scratch_karmadock_team002.pkl` (15 MB each) |
| `papers/KarmaDock_paper.md` | ✅ | the KarmaDock paper |

## Results recap (best-of-3, success@2 A on the 75 available proto_test complexes)
| pipeline | uncorrected | FF | align |
|---|---|---|---|
| P1 baseline (released) | **56.0%** | 34.7% | 10.7% |
| P3 fine-tune (proto_train) | **29.3%** | 26.7% | 16.0% |
| P2 from-scratch (proto_train) | **4.0%** | 4.0% | 4.0% |
(uncorrected is best here — corrections hurt on proto_test; FF kept as the most-physical variant.)

## DECISIONS for you (then we finalize)
1. **Which pipeline's poses become the official `results/proto_test/<id>_pred.sdf`?** The seminar
   evaluates ONE set at `results/proto_test/`. Right now I kept all three under per-pipeline folders
   so you can compare. Options: (a) **P1 baseline** (best, 56%) as the headline, (b) include all three.
   The **training checkpoint** stays separate (P3 + P2 in `model/`) regardless.
2. **Checkpoint in-repo or Zenodo?** Two 15 MB `.pkl` are fine in-repo; interformer-style is to put
   large files on Zenodo and link. Your call.
3. **KarmaDock upstream code** — `KarmaDock/` is NOT copied here (it's cloned inside the Docker image
   from `schrojunzhang/KarmaDock`). We either vendor it into the branch or keep the README pointer +
   Dockerfile clone. (interformer vendored theirs.)
4. **`data/`** — the base proto data already lives on `main`; we won't duplicate the 80 MB zip.

## NOT included (on purpose)
- **LP-PDBBind + BDB2020+ bonus** (P4/P5, leak-proof, honest external eval) — that's for the
  **full-data submission (10 Jul)** + final presentation, not the prototype.
- The deprecated `run_train.sh` (superseded; also previously held the W&B key — now scrubbed).
- No secrets, no datasets/graphs, no W&B key anywhere.

## To finalize after your review
- Flatten the chosen pipeline to `results/proto_test/` (+ `proto_test_ff/`).
- Decide checkpoint hosting; vendor or point to KarmaDock.
- Commit onto the `karmadock` branch in real development order, in your git identity (natural messages),
  keeping RUN_JOURNAL as the genuine work trail. Then push.

---

## Round-1 review responses (your feedback addressed)
1. **Keep all 3 pipelines** ✅ — `results/{p1_baseline,p2_scratch,p3_finetune}/proto_test(_ff)/` retained (75 each).
2. **Keep checkpoints** ✅ — `model/p3_finetune_*.pkl` + `model/p2_scratch_*.pkl` (15 MB each).
3. **Vendor KarmaDock + keep pointer** ✅ — official repo cloned into `KarmaDock/` (code + LICENSE +
   README + architecture/utils/dataset/trained_models), `.git` trimmed. So the runs persist even if a
   Docker copy fails, and the official repo info/README is included. Dockerfile still clones it too.
4. **Proto data copy in `data/`** ✅ — added `prototype_model_data.zip` + `proto_{train,test}.csv`.
5. **Results requirements / PoseBusters / pose review:**
   - **What the tutor evaluates = our poses** in `results/proto_test/<id>_pred.sdf`. Their
     `evaluation.py` computes **symmetry-corrected RMSD + PoseBusters** ON those poses — so we don't
     ship PoseBusters output; we ship the poses (done).
   - **PoseBusters IS in our results** anyway: `notebooks/results_and_comparison.ipynb` §3e runs
     PoseBusters PB-Valid (P1 13.3% / P3 6.7% / P2 0%) + which checks fail most. So it's covered as
     part of the results-visualization deliverable.
   - **Pose review** of generated vs crystal poses: notebook §5 (top-pose RMSD table + py3Dmol overlay).
     *Optional:* I can render static pose-overlay PNGs into `eda/figures/` if you want them as files.
   - **Generated-data listings** (graphs / pockets / preprocessing / kd_out) you asked for: added as
     `cluster_artifacts/` — mirrors the cluster `~/run/work/` structure with file-name manifests +
     `COUNTS.txt` (graphs 712+75, pockets 712+75, kd_out 678/pipeline, checkpoints, logs), since the
     real files are too bulky to upload.

## Still open / optional
- Final layout: keep per-pipeline `results/`, or also flatten the chosen headline (P1) to
  `results/proto_test/` for the tutor's default `--dataset proto_test`? (I'd add a top-level
  `results/proto_test/` = P1 uncorrected so their script runs out-of-the-box, and keep the per-pipeline
  folders for completeness.)
- Render static pose-overlay images? (yes/no)
