# PROVENANCE — what we wrote vs. what is the KarmaDock authors'

**The key point:** the public KarmaDock repo (`schrojunzhang/KarmaDock`, vendored in `KarmaDock/`)
ships **inference code + pretrained weights only — there is NO training script**. So our seminar
contribution is the **training loop, the data adapters, the run wrappers, and the whole HTCondor
orchestration** built *around* KarmaDock. We **call KarmaDock's modules as-is** (model, preprocessing,
docking) — **we did not modify any file inside `KarmaDock/`** (it is cloned fresh in the Dockerfile;
our code lives in `scripts/`).

## 1. Files WE created (our original work)
### `scripts/` (all written by us)
| file | what it does | KarmaDock pieces it calls |
|---|---|---|
| `train.py` | **our main artifact** — a complete checkpointed training/fine-tuning loop (KarmaDock has none). Builds the loop, optimizer, early-stopping, gradient accumulation, val split, W&B, resume. | imports KarmaDock's `KarmaDock` model, `PDBBindGraphDataset`, `PassNoneDataLoader`, and `set_random_seed`/`Early_stopper`/`karmadock_evaluation`; uses the model's own `forward()` losses |
| `convert_seminar_to_karmadock.py` | seminar data layout → KarmaDock layout | — |
| `convert_karmadock_to_seminar.py` | KarmaDock docked poses → seminar `<id>_pred.sdf` (best-first, 3 variants) | reads pose SDFs (RDKit) |
| `preprocess.sh` | wrapper: seminar→KarmaDock layout, then pockets + graphs | calls KarmaDock `utils/pre_processing.py` + `utils/generate_graph.py` |
| `run_train_paper.sh` | Pipeline 2 (from scratch) — paper's 2-stage protocol | calls our `train.py` |
| `run_finetune.sh` | Pipeline 3 (fine-tune the released ckpt) | calls our `train.py` |
| `run_infer.sh` | wrapper: dock + score + correct, then export poses | calls KarmaDock `utils/ligand_docking.py` + our converter |

### `condor/` (all written by us)
| file | job |
|---|---|
| `preprocess_train.sub`, `preprocess_test.sub` | CPU — build graphs |
| `p1_infer_baseline.sub` | GPU — Pipeline 1 (released weights, inference only) |
| `p2_train_scratch.sub` | GPU — Pipeline 2 training (2-stage from scratch) |
| `p3_finetune.sub` | GPU — Pipeline 3 fine-tune |
| (`p2_infer.sub`, `p3_infer.sub`) | GPU — dock proto_test with each trained checkpoint |

### Other ours
- `Dockerfile` — builds the image (clones KarmaDock, installs the authors' packed conda env, adds our `scripts/`).
- the notebooks (`results_and_comparison.ipynb`, `eda/data_exploration.ipynb`), all docs, and `cluster_artifacts/` manifests.

## 2. KarmaDock authors' code we USE (unmodified, in `KarmaDock/`)
| KarmaDock file | what it provides | used by |
|---|---|---|
| `architecture/KarmaDock_architecture.py` | the `KarmaDock` model (EGNN + GVP/GT encoders + MDN); its `forward()` returns the RMSD + MDN losses | our `train.py` |
| `dataset/graph_obj.py` | `PDBBindGraphDataset` (loads `.dgl` graphs, re-randomises start pose) | our `train.py` |
| `dataset/dataloader_obj.py` | `PassNoneDataLoader` | our `train.py` |
| `utils/fns.py` | `set_random_seed`, `Early_stopper`, `karmadock_evaluation` | our `train.py` |
| `utils/pre_processing.py` | 12 Å pocket extraction (prody) | our `preprocess.sh` |
| `utils/generate_graph.py` | builds per-complex `.dgl` graphs | our `preprocess.sh` |
| `utils/ligand_docking.py` | docking + MDN scoring + FF/align pose correction | our `run_infer.sh` |
| `trained_models/karmadock_screening.pkl` | the **released pretrained weights** (the authors') | P1 baseline; init for P3 fine-tune |

## 3. Summary of contribution
- **Authors':** the KarmaDock model + preprocessing/docking utilities + released weights (used as-is).
- **Ours:** `train.py` (there was no trainer), the seminar↔KarmaDock data adapters, the P1/P2/P3 run
  wrappers, every condor `.sub`, the Docker build, and all analysis/EDA/docs. No KarmaDock source was edited.

*(Bonus work for the full-data/final submission — `lp_to_seminar.py`, `bdb_to_seminar.py`,
`run_train_lp_scratch.sh`, `ddp_smoke.sh`, the LP/BDB condor subs, the DDP additions to `train.py`,
and the analysis/EDA notebooks — is also entirely ours; it is not part of this prototype package.)*
