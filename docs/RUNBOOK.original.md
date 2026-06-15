# Cluster runbook — KarmaDock prototype (team002)

Everything you run is below. Nothing here touches the cluster on its own — you
execute each step. Commands assume the SIC HPC (conduit / HTCondor docker universe).

Layout used throughout (all under your `$HOME = /home/bdldt_team002`):

```
$HOME/run/
├── data/proto/         proto_train/  proto_test/  proto_train.csv  proto_test.csv   (from prototype_model_data.zip)
├── work/               complex/  graphs/  ckpt/  kd_out/                            (created by the jobs)
├── results/            proto_test/                                                  (predicted SDFs)
└── logs/                                                                            (condor .out/.err/.log)
```

---

## 0. One-time: build & push the Docker image (on your laptop, needs Docker)

> **You are on a Mac M1 (arm64); the cluster is x86_64 (amd64).** You MUST cross-build
> for `linux/amd64`, or Condor will reject the image on the workers
> ("exec format error"). Use `docker buildx` with an explicit `--platform`.

```bash
cd karmadock-seminar
docker login -u ahlamloum

# one-time: a builder that can emulate amd64 (uses QEMU, already in Docker Desktop)
docker buildx create --name xbuilder --use 2>/dev/null || docker buildx use xbuilder

# cross-build FOR THE CLUSTER and push in one step
docker buildx build --platform linux/amd64 \
  -t ahlamloum/karmadock-seminar:v2 \
  -f docker/Dockerfile --push .
```

`buildx ... --push` builds and pushes together (a plain `docker push` afterwards isn't
needed). Verify the architecture landed correctly:

```bash
docker buildx imagetools inspect ahlamloum/karmadock-seminar:v2 | grep -i platform
# expect:  Platform:  linux/amd64
```

Notes:
- The image installs the authors' **pre-packed** conda env from Zenodo (no conda
  solver), which avoids the `cannot allocate memory` / `Killed` error the yaml route
  hits under QEMU on Apple Silicon.
- Still give Docker Desktop enough RAM (**Settings → Resources → Memory ≥ 8 GB**) and
  free disk — the pack + CUDA layers are several GB, and emulated amd64 is slower than
  native.
- The image name is already set in all three `condor/*.sub` files.

> The build runs a sanity import of torch/torch_geometric/rdkit/MDAnalysis/prody,
> so a broken env fails the build rather than a cluster job. If the upstream
> `karmadock_env.yaml` fails to solve, see README "Docker notes".

## 1. One-time: stage data + code on the cluster

```bash
# from your laptop
scp -r karmadock-seminar bdldt_team002@conduit.hpc.uni-saarland.de:~/run_code
# unzip the tutor's data into the expected place
ssh bdldt_team002@conduit.hpc.uni-saarland.de
mkdir -p ~/run/data ~/run/work ~/run/results ~/run/logs
cd ~/run/data && unzip /path/to/prototype_model_data.zip   # -> gives proto/ with train/test + csvs
# adjust paths if the zip extracts a different folder name
```

The `condor/*.sub` files reference `/app/scripts/*` (baked into the image) and your
`/home/.../run/...` data via the NFS `+WantGPUHomeMounted` mount — no file transfer.

## 2. Preprocess (CPU): pockets + graphs — run once per dataset

`condor/preprocess.sub` is set for **proto_train**. Submit it, then edit the four
`arguments` paths to point at **proto_test** and submit again:

```bash
cd ~/run_code/karmadock-seminar/condor
condor_submit preprocess.sub                      # proto_train
# edit arguments: proto_train -> proto_test (csv, src, complex, graphs), then:
condor_submit preprocess.sub                      # proto_test
condor_q                                           # watch; check logs/preprocess.*.err
```

Sanity check when done: `ls ~/run/work/graphs/proto_train | wc -l` (should be a few
hundred `.dgl` files; some complexes drop out if rdkit can't build a conformer).

## 3a. Baseline inference (GPU) — pretrained model + FF/align correction

`condor/infer.sub` is preset to dock with the **baseline** `karmadock_screening.pkl`:

```bash
condor_submit infer.sub
# outputs: ~/run/results/proto_test/*_pred.sdf  and  ~/run/work/kd_out/proto_test/<re>.csv
```

This alone gives you a complete, submittable predicted-poses ZIP + the notebook plots.

## 3b. Retrain / fine-tune (GPU) — produces OUR checkpoint

**W&B (optional, recommended):** the secret is read from the submit-node env, never
stored in a file. On the conduit login node, before submitting:

```bash
export WANDB_API_KEY=<your_rotated_key>      # NOT your old, exposed key
# if the worker nodes have no outbound internet, also run training offline:
# export WANDB_MODE=offline                   # then later, from a node with net: wandb sync <out_dir>/wandb/offline-*
```

`train.sub` forwards `WANDB_API_KEY`/`WANDB_MODE` into the container and names the run
`proto_scratch`; `run_train.sh` auto-enables `--wandb` only when a key (or offline mode)
is present. Metrics (train/val loss, rmsd, mdn, lr) log per epoch and the best
checkpoint is uploaded as a W&B artifact.

```bash
# from scratch (train.sub is preset to this; 5th arg empty)
condor_submit train.sub
# -> ~/run/work/ckpt/proto_scratch/karmadock_team002.pkl  (best)  + last.pt (resume)

# to ALSO have a fine-tuned variant: copy train.sub to train_ft.sub, set out dir to
# .../ckpt/proto_ft and append the 5th argument:
#   /app/KarmaDock/trained_models/karmadock_screening.pkl
condor_submit train_ft.sub
```

`train.py` checkpoints every epoch and `--resume` is on, so if a modern node
force-reschedules the job it picks up from `last.pt`.

## 3c. Inference with OUR checkpoint

Copy `infer.sub` to `infer_ours.sub`, change the **3rd** argument to
`/home/bdldt_team002/run/work/ckpt/proto_scratch/karmadock_team002.pkl`
and the 5th to `.../results/proto_test_ours`, then `condor_submit infer_ours.sub`.

## 4. Visualize + evaluate

```bash
# locally or via Code Server (ood.hpc.uni-saarland.de):
jupyter notebook notebooks/results_visualization.ipynb   # set KD_OUT to the kd_out dir
# official metrics (from the seminar repo root):
python evaluation/evaluation.py --dataset proto_test
```

## 5. Assemble the prototype submission (due 19 June)

- [ ] source code (this repo, documented) → GitHub
- [ ] training checkpoint → `karmadock_team002.pkl`
- [ ] results notebook → `notebooks/results_visualization.ipynb`
- [ ] predicted poses → `zip -r proto_test_poses.zip ~/run/results/proto_test`
- [ ] Docker image name → `ahlamloum/karmadock-seminar:v2`
- [ ] Condor files → `condor/*.sub` **plus the `logs/*.log/.out/.err` from your real runs**

## Debugging quickies
- `condor_q -hold <jobid>` — why a job is held (missing file, bad image, etc.)
- `condor_q -analyze <jobid>` — why it isn't matching a node
- job stuck idle forever → usually an over-tight `requirements`/resource request
- import errors in `logs/*.err` → the image env is wrong; fix Dockerfile, rebuild, repush
