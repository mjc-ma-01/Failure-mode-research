#!/usr/bin/env bash
# AD 的 SHE 进化链（**GPU 作业**，本地 Qwen）：进程不在就重启（断点续跑），result_table.json 出现即退出。
# 用法：setsid nohup bash she_rjob_chain.sh <workdir> [epochs] [candidates] [seed_dir] &
set -uo pipefail
PROJ=/mnt/shared-storage-user/ai4good1-share/majiachen/Failure-mode-research
WD="${1:?workdir}"; EPOCHS="${2:-3}"; CANDS="${3:-2}"
SEEDDIR="${4:-evolve/harness/configs/harness/SHE_agentdojo_seed_allwarn}"
PY=/mnt/shared-storage-user/ai4good1-share/majiachen/.venvs/fmr-api/bin/python

export https_proxy=http://127.0.0.1:28084 http_proxy=http://127.0.0.1:28084
export no_proxy="localhost,127.0.0.1,0.0.0.0,::1" NO_PROXY="localhost,127.0.0.1,0.0.0.0,::1"
export FMR_SKIP_PYLIBS=1
export PYTHONPATH="evolve/harness/src:evolve/harness/scripts"
LOG="/tmp/fmr_rjob_$(basename "$WD").log"
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }
say "启动 AD 守护（GPU/rjob）：workdir=$WD epochs=$EPOCHS candidates=$CANDS seed=$SEEDDIR"

while true; do
  if [ -f "$PROJ/$WD/result_table.json" ]; then
    say "✅ 已完成（result_table.json 存在），守护退出"; exit 0
  fi
  if pgrep -f "she_evolve_v2.py .*--workdir $WD" >/dev/null; then
    sleep 120; continue
  fi
  say "编排器不在运行 → 重启（续跑）"
  ( cd "$PROJ" && "$PY" -u evolve/harness/scripts/she_evolve_v2.py \
      --execute rjob --epochs "$EPOCHS" --candidates "$CANDS" --seeds 0 1 2 --stale-stop 2 \
      --seed-dir "$SEEDDIR" --calibration /tmp/_no_calibration_.json \
      --workdir "$WD" ) >> "$LOG" 2>&1 || say "编排器退出（非 0），60s 后重试"
  sleep 60
done
