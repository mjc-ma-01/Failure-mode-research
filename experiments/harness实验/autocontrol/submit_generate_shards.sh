#!/usr/bin/env bash
set -euo pipefail

DRY_RUN="${1:-false}"
ROOT=/mnt/shared-storage-user/majiachen/Failure-mode-research
LAUNCH="$ROOT/experiments/harness实验/autocontrol/launch_generate_shard.sh"
IMAGE=registry.h.pjlab.org.cn/ailab-safeag/lixiangtian:20260117023216

for SHARD_ID in 0 1 2 3 4 5; do
  rjob submit \
    --name "harness-ac-full-gen-s${SHARD_ID}" \
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
    --env SHARD_ID="$SHARD_ID" \
    -- bash "$LAUNCH"
done
