# `results/` — predicted docking poses

This folder holds KarmaDock's predicted ligand poses for the `proto_test` set,
ready for the seminar evaluation script. Each pose file is a multi-conformer SDF
named `<id>_pred.sdf`, with the **best-ranked pose first** (the tutor scores
top-1 by default; use `--top_n N` for best-of-N).

## What to evaluate

```
results/proto_test/          ← evaluate THIS (the official submission)
```

This is the single set the tutor runs:
`python evaluation/evaluation.py --dataset proto_test`.
It is the **P1 baseline** (released KarmaDock weights), **uncorrected** poses —
the variant that scored best for us on proto_test (see `docs/`).

## Layout

```
results/
├── proto_test/                 ← official set the tutor evaluates (P1, uncorrected, 75 files)
├── p1_baseline/                ← released weights, inference only
│   ├── proto_test/             ←   uncorrected poses (75)  ← identical source as ./proto_test/
│   └── proto_test_ff/          ←   FF-corrected poses (75) — most physically plausible (per paper)
├── p2_scratch/                 ← our model trained from scratch on proto_train
│   ├── proto_test/             ←   uncorrected (75)
│   └── proto_test_ff/          ←   FF-corrected (75)
└── p3_finetune/                ← released weights fine-tuned on proto_train
    ├── proto_test/             ←   uncorrected (75)
    └── proto_test_ff/          ←   FF-corrected (75)
```

The top-level `proto_test/` is a copy of `p1_baseline/proto_test/`, promoted so
`evaluation.py --dataset proto_test` runs out of the box. The three per-pipeline
folders are kept for **comparison only** — they are not the submission.

## Reading the file names

`<pdbid>_<ligand>_<chain>_<resnum>_pred.sdf`, e.g. `3ix2_AC2_A_302_pred.sdf`.
Each file is **one complex**. Several files sharing a PDB id (e.g. `3ix2_AC2_A_302`,
`3ix2_AC2_B_302`) are **different binding sites / chains, not duplicates**.

## The three pipelines (what to compare)

| folder | model | how it was produced |
|---|---|---|
| `p1_baseline` | released `karmadock_screening.pkl` | inference only (no training) |
| `p2_scratch`  | our weights | trained from scratch on `proto_train` |
| `p3_finetune` | our weights | released weights fine-tuned on `proto_train` |

## Pose variants

- **`proto_test/`** — *uncorrected* docked poses (KarmaDock's raw output). Best
  accuracy on this set.
- **`proto_test_ff/`** — *force-field corrected* poses. Slightly less accurate by
  RMSD here, but the most physically plausible variant (the paper recommends FF).

Numbers, plots, and PoseBusters validity are in `notebooks/` and `docs/`.
