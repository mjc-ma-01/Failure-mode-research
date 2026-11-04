#!/usr/bin/env bash
# AgentHarm SHE 进化链（**宿主机 API 通道**，无 GPU）：victim = 网关 Qwen/Qwen3.5-9B。
# 用法：setsid nohup bash she_ah_api_chain.sh <workdir> [epochs] [candidates] [seed_dir] &
set -uo pipefail
PROJ=/mnt/shared-storage-user/ai4good1-share/majiachen/Failure-mode-research
WD="${1:?workdir}"; EPOCHS="${2:-3}"; CANDS="${3:-2}"
SEEDDIR="${4:-evolve/harness/configs/harness/SHE_agentharm_seed}"
WORKERS="${WORKERS:-16}"
PY=/mnt/shared-storage-user/ai4good1-share/majiachen/.venvs/fmr-api/bin/python

export https_proxy=http://127.0.0.1:28084 http_proxy=http://127.0.0.1:28084
export no_proxy="localhost,127.0.0.1,0.0.0.0,::1" NO_PROXY="localhost,127.0.0.1,0.0.0.0,::1"
export FMR_SKIP_PYLIBS=1
export PYTHONPATH="evolve/harness/src:evolve/harness/scripts"
LOG="/tmp/fmr_ah_api_$(basename "$WD").log"
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }
say "启动 AH 守护：workdir=$WD epochs=$EPOCHS candidates=$CANDS seed=$SEEDDIR workers=$WORKERS"

while true; do
  if [ -f "$PROJ/$WD/result_table.json" ]; then
    say "✅ 已完成（result_table.json 存在），守护退出"; exit 0
  fi
  if pgrep -f "she_ah_orchestrator.py .*--workdir $WD" >/dev/null; then
    sleep 120; continue
  fi
  say "编排器不在运行 → 重启（续跑模式）"
  ( cd "$PROJ" && "$PY" -u evolve/harness/scripts/she_ah_orchestrator.py \
      --execute local --workers "$WORKERS" --epochs "$EPOCHS" --candidates "$CANDS" \
      --stale-stop 2 --seed-dir "$SEEDDIR" --workdir "$WD" ) >> "$LOG" 2>&1 \
    || say "编排器退出（非 0），60s 后重试"
  sleep 60
done
