#!/usr/bin/env bash
# 串行接力：等 <前一个作业> 结束后，提交 AgentDojo 进化作业（避免两张卡同时跑）。
# 用法：setsid nohup bash chain_evolve_after.sh <前一个作业名> [rounds] &
set -uo pipefail
PREV="${1:?前一个作业名}"
ROUNDS="${2:-3}"
PROJ=/mnt/shared-storage-user/ai4good1-share/majiachen/Failure-mode-research
LOG=/tmp/fmr_chain.log
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

say "等待 $PREV 结束…"
while true; do
  state="$(cd /tmp && timeout 120 rjob list 2>/dev/null | grep -E "rjob $PREV:" | tail -1)"
  case "$state" in
    *Succeeded*|*Failed*|*Stopped*) say "$PREV → $state"; break ;;
    *) sleep 180 ;;
  esac
done
say "提交 AgentDojo 进化作业（rounds=$ROUNDS）"
cd "$PROJ" || exit 1
FMR_RUN_SCRIPT=run_agentdojo_evolution.sh bash evolve/harness/scripts/submit_gpu_job.sh 32 "$ROUNDS" >>"$LOG" 2>&1
JOB="$(cat /tmp/fmr_last_job 2>/dev/null || echo '?')"
say "新作业：$JOB（进化循环，heldout 会在作业内自动评）"
