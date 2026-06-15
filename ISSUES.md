# Issues & fixes (short)

The condensed version of our dev log — just the bugs/problems we hit and how we solved them.
(The full chronological journal isn't shared; this is the part worth reviewing.)

## Setup / environment
- **Fake `ModuleNotFoundError: pandas`.** A `bash -l` login shell re-activated conda's *base*
  env and shadowed KarmaDock's `python3`. Fix: never wrap the scripts in a login shell (the
  cluster execs them directly, so it's fine there).
- **`dgl` / `openbabel` "missing".** Harmless — KarmaDock never imports them (the `.dgl`
  extension is just a filename).
- **CPU OOM training locally.** `batch_size 16` hit ~10 GB and got OOM-killed on a 14 GB
  laptop. Local-only; the cluster trains on GPU. Use a tiny batch for local smoke tests.

## Cluster / HTCondor
- **`transfer_input_files = scripts/` flattened the dir** → Python couldn't find the converter
  (`can't open .../scripts/convert_*.py`). Fix: keep code in the Docker image + mount `/home`
  (`+WantGPUHomeMounted`), no file transfer.
- **Impossible GPU pin.** `CUDADeviceName == "Tesla V100-PCIE-32GB"` never matched (cluster
  V100s are 16 GB) → job idle forever. Fix: just `request_gpus = 1`.
- **Missing `requirements = UidDomain == "cs.uni-saarland.de"`** (needed with
  `+WantGPUHomeMounted` for the home mount / run-as-user). Added to all subs.
- **`generate_graph.py` takes no `--n_job` flag** — the old wrapper passed one. Removed.
- **Node lottery / `idun`.** A docking epoch took 17–84 min on the contended `idun` teaching
  node vs ~82 s on a good node, and `idun` also threw an NFS `torch.save` I/O error that killed
  a run. Fix: exclude it — `requirements = … && (Machine =!= "idun.hpc.uni-saarland.de")`.
- **Multi-GPU queue starvation.** `request_gpus=2/4` jobs sat idle for hours (few nodes with
  several free GPUs). Pivoted the prototype to single-GPU; kept the DDP code for the full run.

## Data
- **proto_test gap.** The CSV lists 118 complexes but only **75** have structures in the
  provided folder — verified it's the dataset as given (same gap locally), not our bug. We
  benchmark on the 75 and will raise the missing 43 with the tutors.
- **PDBBind ligand sanitization (full-data prep).** ~14% of ligands fail RDKit
  kekulize/valence on the as-given `.sdf`. Idea for later: re-assign bond orders from SMILES.

## Results / evaluation
- **Corrections hurt on proto_test.** Unlike the paper, FF/align post-processing *lowers*
  accuracy here (P1 56→34.7→10.7%). So we submit the **uncorrected** poses; `run_infer.sh`
  defaults to `align_corrected`, so the submitted set must be re-exported `--mode uncorrected`.
- **Two different RMSDs.** PoseBusters' symmetry-corrected RMSD ≠ KarmaDock's internal RMSD;
  the tutor's `evaluation.py` uses symmetry-corrected, so treat its output as the official number.

## Tooling
- **W&B run-id collision.** The run id was a hash of the output dir, so a resubmitted job
  silently overwrote the old run. Fix: unique `name_timestamp_pid` id saved to a file.
- **W&B off by default.** No `WANDB_API_KEY` is baked in; the key is passed at submit time via
  `condor_submit -a 'environment="WANDB_API_KEY=…"'`, so it never lands in the repo.
