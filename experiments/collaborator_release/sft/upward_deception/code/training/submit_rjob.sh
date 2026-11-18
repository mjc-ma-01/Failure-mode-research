#!/usr/bin/env bash
set -euo pipefail

DRY_RUN="${1:-false}"
JOB_NAME="${JOB_NAME:-upward-sft-qwen35-9b-v1}"
RUN_NAME="${RUN_NAME:-qwen35_9b_lora_v1}"
IMAGE=registry.h.pjlab.org.cn/ailab-safeag/lixiangtian:20260117023216
LAUNCH=/mnt/shared-storage-user/majiachen/Failure-mode-research/experiments/model_vs_harness_sft/upward_deception/training/launch_job.sh

rjob submit \
  --name "$JOB_NAME" \
  --group safevlagent_gpu_pool \
  --namespace ailab-safevlagent \
  --dry-run "$DRY_RUN" \
  --charged-group safevlagent_gpu_pool \
  --restart-policy never \
  --auto-restart false \
  --backoff_limit 1 \
  --private-machine group \
  --share-host-shm true \
  --image "$IMAGE" \
  --cpu 8 \
  --gpu 1 \
  --memory 65536 \
  --custom-resources brainpp.cn/fuse=1 \
  --mount \
    gpfs://gpfs1/majiachen:/mnt/shared-storage-user/majiachen \
    gpfs://gpfs1/ai4good1-share:/mnt/shared-storage-user/ai4good1-share \
    gpfs://gpfs2/gpfs2-shared-public/huggingface:/mnt/shared-storage-gpfs2/gpfs2-shared-public/huggingface \
    gpfs://gpfs2/ai4good1-share-gpfs2:/mnt/shared-storage-gpfs2/ai4good1-share-gpfs2 \
  --env RUN_NAME="$RUN_NAME" \
  -- bash "$LAUNCH"
