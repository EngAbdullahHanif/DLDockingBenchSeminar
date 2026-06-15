# KarmaDock image (BDLDT team002)
# Reproducible build: clones upstream KarmaDock, creates its conda env, adds our
# train/infer/convert scripts. Plain `python3` resolves to the karmadock env, so
# HTCondor's docker universe can run our shell scripts with no activation step.
#
# The cluster is x86_64 (amd64). On an Apple Silicon (arm64) Mac you MUST cross-build
# for linux/amd64 or Condor can't run the image:
#   docker buildx build --platform linux/amd64 \
#     -t ahlamloum/karmadock-seminar:v2 -f docker/Dockerfile --push .
# Verify:  docker buildx imagetools inspect ahlamloum/karmadock-seminar:v2 | grep -i platform
#
# NOTE: GPU userspace (pytorch + cudatoolkit) comes from the conda env; the host
# driver is injected by Condor at run time.
#
# We use the authors' PRE-PACKED conda env (conda-pack tarball on Zenodo) instead of
# `conda env create -f karmadock_env.yaml`. The yaml route runs conda's dependency
# solver, which is memory-hungry and gets OOM-killed under QEMU emulation on Apple
# Silicon ("Collecting package metadata ... Killed"). The pack is a ready-built
# linux-64 env: just download + extract + conda-unpack. No solving, lower risk.

FROM continuumio/miniconda3:23.10.0-1

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        git wget ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1) upstream KarmaDock source + pretrained checkpoints
RUN git clone https://github.com/schrojunzhang/KarmaDock.git /app/KarmaDock
# RUN cd /app/KarmaDock && git checkout <COMMIT_SHA>   # pin once a build is verified

# 2) authors' pre-packed conda env (linux-64) -> /opt/conda/envs/karmadock
#    Download the tarball ONCE to docker/ before building (keeps the build offline & fast):
#      curl -L -o docker/karmadock_env.tar.gz \
#        "https://zenodo.org/record/7788732/files/karmadock_env.tar.gz?download=1"
#    The build context is the repo root, so the file is at docker/karmadock_env.tar.gz.
COPY docker/karmadock_env.tar.gz /tmp/karmadock_env.tar.gz
RUN mkdir -p /opt/conda/envs/karmadock && \
    tar -xzf /tmp/karmadock_env.tar.gz -C /opt/conda/envs/karmadock && \
    rm /tmp/karmadock_env.tar.gz && \
    /opt/conda/envs/karmadock/bin/conda-unpack

# 3) extra pip deps imported by our/the code but not in the pack
RUN /opt/conda/envs/karmadock/bin/pip install --no-cache-dir prefetch_generator rmsd wandb

# 4) our scripts (converters, train.py, run_*.sh)
COPY scripts/ /app/scripts/
RUN chmod +x /app/scripts/*.sh

# make the karmadock env the default python and put KarmaDock on the path
ENV PATH=/opt/conda/envs/karmadock/bin:$PATH
ENV PYTHONPATH=/app/KarmaDock

# sanity check at build time (fails the build early if deps are wrong)
RUN python3 -c "import torch, torch_geometric, rdkit, MDAnalysis, prody; \
print('torch', torch.__version__, '| rdkit', rdkit.__version__)"

WORKDIR /app
CMD ["/bin/bash"]
