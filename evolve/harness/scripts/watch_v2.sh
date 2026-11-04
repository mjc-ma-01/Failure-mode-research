#!/usr/bin/env bash
# v2 进化守护：进程不在就重启（脚本自身可断点续跑）；作业失败由编排器内部重试/续跑。
# 用法：setsid nohup bash watch_v2.sh <workdir> [epochs] [candidates] &
set -uo pipefail
PROJ=/mnt/shared-storage-user/ai4good1-share/majiachen/Failure-mode-research
WD="${1:?workdir}"; EPOCHS="${2:-4}"; CANDS="${3:-3}"
LOG=/tmp/fmr_v2_watch.log
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }
while true; do
  if pgrep -f "she_evolve_v2.py .*--workdir $WD" >/dev/null; then
    sleep 120; continue
  fi
  if [ -f "$PROJ/$WD/result_table.json" ]; then
    say "✅ 已完成（result_table.json 存在），守护退出"
    exit 0
  fi
  say "编排器不在运行 → 重启（续跑模式：$WD）"
  ( cd "$PROJ" && env PYTHONPATH="evolve/harness/src:evolve/harness/scripts" \
      python3 -u evolve/harness/scripts/she_evolve_v2.py --epochs "$EPOCHS" --candidates "$CANDS" \
      --seeds 0 1 2 --stale-stop 2 --workdir "$WD" >> "$LOG" 2>&1 ) || say "编排器退出（非 0），10 分钟后重试"
  sleep 600
done
