#!/usr/bin/env bash
# 一键提交 GPU 作业（防重复提交 + gpu.py --strict-job 包裹 + 自适应并发）。
# 用法：bash submit_gpu_job.sh [初始workers] [seeds...]
set -uo pipefail
PROJ=/mnt/shared-storage-user/ai4good1-share/majiachen/Failure-mode-research
WORKERS="${1:-32}"; shift || true
SEEDS=("$@"); [ ${#SEEDS[@]} -eq 0 ] && SEEDS=(0)

# 防重复：同一时刻只允许一个提交（上次就是重复提交白占了一张卡）
exec 9>/tmp/fmr_rjob_submit.lock
flock -n 9 || { echo "已有提交在进行（锁被占用），退出"; exit 1; }

# 作业入口脚本：默认 run_sweep.sh；FMR_RUN_SCRIPT=xxx.sh 时跑别的（如 run_agentdojo_evolution.sh）
RUN_SH="$PROJ/evolve/harness/scripts/${FMR_RUN_SCRIPT:-run_sweep.sh}"
# 作业名可由调用方指定（并发多条链时必须唯一，否则 /tmp/fmr_last_job 会串）
NAME="${FMR_JOB_NAME:-fmr-gpu-pilot-$(date +%m%d%H%M)}"
echo "[submit] $NAME workers=$WORKERS seeds=${SEEDS[*]} entry=$(basename "$RUN_SH")"
if ! rjob submit --name="$NAME" --namespace=ailab-safevlagent --gpu=1 --cpu=16 --memory=131072 \
  --charged-group=safevlagent_gpu --private-machine=group \
  --image=registry.h.pjlab.org.cn/ailab-safeag/lixiangtian:20260117023216 \
  --restart-policy=never --auto-restart=false --backoff_limit=1 \
  --host-network=false --share-host-shm=true \
  --mount=gpfs://gpfs1/majiachen:/mnt/shared-storage-user/majiachen \
  --mount=gpfs://gpfs1/ai4good1-share:/mnt/shared-storage-user/ai4good1-share \
  --mount=gpfs://gpfs2/gpfs2-shared-public/huggingface:/mnt/shared-storage-gpfs2/gpfs2-shared-public/huggingface \
  --mount=gpfs://gpfs2/ai4good1-share-gpfs2:/mnt/shared-storage-gpfs2/ai4good1-share-gpfs2 \
  --custom-resources brainpp.cn/fuse=1 \
  -- /usr/bin/env ${FMR_SOURCES:+FMR_SOURCES="$FMR_SOURCES"} ${FMR_AC_SPEC_DIR:+FMR_AC_SPEC_DIR="$FMR_AC_SPEC_DIR"} ${FMR_SHE_MANIFEST:+FMR_SHE_MANIFEST="$FMR_SHE_MANIFEST"} --chdir="$PROJ" \
     /usr/bin/timeout --signal=TERM --kill-after=60s 9000s \
     /bin/bash "$RUN_SH" 8000 "$WORKERS" "${SEEDS[@]}"; then
  echo "SUBMIT_FAILED"
  exit 1
fi
# 注意：**不要**在这里包 /mnt/shared-storage-user/majiachen/gpu.py——它要求平台预设
# CUDA_VISIBLE_DEVICES（本容器不设），会在容器启动自检时以 exit 5 直接失败。
echo "$NAME" > /tmp/fmr_last_job
echo "JOB_NAME=$NAME"
