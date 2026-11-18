#!/usr/bin/env bash
set -euo pipefail

DRY_RUN="${1:-false}"
ARM_SLUGS="${2:-m,react,react_safe}"
JOB_TAG="${3:-}"
SHARD_IDS="${4:-0,1,2}"
ROOT=/mnt/shared-storage-user/majiachen/Failure-mode-research
LAUNCH="$ROOT/experiments/harness实验/autocontrol/launch_monitor_shard.sh"
IMAGE=registry.h.pjlab.org.cn/ailab-safeag/lixiangtian:20260117023216

IFS=',' read -r -a REQUESTED_ARMS <<< "$ARM_SLUGS"
IFS=',' read -r -a REQUESTED_SHARDS <<< "$SHARD_IDS"
for ARM_SLUG in "${REQUESTED_ARMS[@]}"; do
  case "$ARM_SLUG" in
    m) JOB_ARM=m ;;
    react) JOB_ARM=r ;;
    react_safe) JOB_ARM=rs ;;
  esac
  for SHARD_ID in "${REQUESTED_SHARDS[@]}"; do
    rjob submit \
      --name "hacf-mon-${JOB_ARM}${JOB_TAG}-s${SHARD_ID}" \
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
      --env ARM_SLUG="$ARM_SLUG" --env SHARD_ID="$SHARD_ID" \
      -- bash "$LAUNCH"
  done
done
