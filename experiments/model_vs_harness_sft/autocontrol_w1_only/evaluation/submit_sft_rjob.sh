#!/usr/bin/env bash
set -euo pipefail

DRY_RUN="${1:-false}"
ROOT=/mnt/shared-storage-user/majiachen/Failure-mode-research
LAUNCH="$ROOT/experiments/model_vs_harness_sft/autocontrol_w1_only/evaluation/launch_sft.sh"
IMAGE=registry.h.pjlab.org.cn/ailab-safeag/lixiangtian:20260117023216

rjob submit \
  --name autocontrol-w1-only-eval-final \
  --group safevlagent_gpu_pool --namespace ailab-safevlagent \
  --dry-run "$DRY_RUN" --charged-group safevlagent_gpu_pool \
  --restart-policy never --auto-restart false --backoff_limit 1 \
  --private-machine group --share-host-shm true \
  --image "$IMAGE" --cpu 8 --gpu 1 --memory 65536 \
  --custom-resources brainpp.cn/fuse=1 \
  --mount \
    gpfs://gpfs1/majiachen:/mnt/shared-storage-user/majiachen \
    gpfs://gpfs1/ai4good1-share:/mnt/shared-storage-user/ai4good1-share \
    gpfs://gpfs2/gpfs2-shared-public/huggingface:/mnt/shared-storage-gpfs2/gpfs2-shared-public/huggingface \
    gpfs://gpfs2/ai4good1-share-gpfs2:/mnt/shared-storage-gpfs2/ai4good1-share-gpfs2 \
  -- bash "$LAUNCH"
