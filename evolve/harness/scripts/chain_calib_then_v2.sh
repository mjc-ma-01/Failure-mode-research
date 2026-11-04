#!/usr/bin/env bash
# 接力：等 allwarn seed 标定完成 → 用标定选定的 seed 启动 v2 进化（带守护）。
set -uo pipefail
PROJ=/mnt/shared-storage-user/ai4good1-share/majiachen/Failure-mode-research
CAL="$PROJ/experiments/she_agentdojo_calibration_allwarn/calibration.json"
LOG=/tmp/fmr_chain_v2.log
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }
say "等待标定结果：$CAL"
for i in $(seq 1 240); do [ -f "$CAL" ] && break; sleep 60; done
if [ ! -f "$CAL" ]; then say "标定超时（4h）→ 退出"; exit 2; fi
SEED=$(python3 -c "import json;print(json.load(open('$CAL'))['chosen_seed_dir'])")
say "标定完成，seed=$SEED → 启动 v2 进化（守护模式）"
cd "$PROJ" || exit 1
setsid nohup bash evolve/harness/scripts/watch_v2.sh experiments/she_agentdojo_v2 3 2 >> "$LOG" 2>&1 &
sleep 5
say "v2 守护已启动；日志 /tmp/fmr_v2_watch.log"
