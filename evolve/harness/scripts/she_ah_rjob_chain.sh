#!/usr/bin/env bash
# AH 的 SHE 进化链（**GPU 作业**，本地 Qwen）；进程不在就重启，result_table.json 出现即退出。
set -uo pipefail
PROJ=/mnt/shared-storage-user/ai4good1-share/majiachen/Failure-mode-research
WD="${1:?workdir}"; EPOCHS="${2:-3}"; CANDS="${3:-2}"
SEEDDIR="${4:-evolve/harness/configs/harness/SHE_agentharm_seed_allwarn}"
PY=/mnt/shared-storage-user/ai4good1-share/majiachen/.venvs/fmr-api/bin/python
export https_proxy=http://127.0.0.1:28084 http_proxy=http://127.0.0.1:28084
export no_proxy="localhost,127.0.0.1" NO_PROXY="localhost,127.0.0.1"
export FMR_SKIP_PYLIBS=1 PYTHONPATH="evolve/harness/src:evolve/harness/scripts"
LOG="/tmp/fmr_ah_rjob_$(basename "$WD").log"
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }
say "启动 AH 守护（GPU/rjob）：workdir=$WD epochs=$EPOCHS candidates=$CANDS"
while true; do
  if [ -f "$PROJ/$WD/result_table.json" ]; then say "✅ 完成"; exit 0; fi
  if pgrep -f "she_ah_orchestrator.py .*--workdir $WD" >/dev/null; then sleep 120; continue; fi
  say "编排器不在运行 → 重启（续跑）"
  ( cd "$PROJ" && "$PY" -u evolve/harness/scripts/she_ah_orchestrator.py \
      --execute rjob --epochs "$EPOCHS" --candidates "$CANDS" --stale-stop 2 \
      --seed-dir "$SEEDDIR" --workdir "$WD" ) >> "$LOG" 2>&1 \
    || say "编排器退出（非 0），60s 后重试"
  sleep 60
done
