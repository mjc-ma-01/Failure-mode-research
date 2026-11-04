#!/usr/bin/env bash
# 守护一轮实验：盯着 rjob 状态 → 失败自动重提 → 成功自动跑 finalize_run.py。
# 用法：setsid nohup bash evolve/harness/scripts/watch_and_finalize.sh <job_name> [workers] [seeds...]
set -uo pipefail
JOB="${1:?job name}"; shift || true
WORKERS="${1:-32}"; shift || true
SEEDS=("$@"); [ ${#SEEDS[@]} -eq 0 ] && SEEDS=(0)
PROJ=/mnt/shared-storage-user/ai4good1-share/majiachen/Failure-mode-research
LOG=/tmp/fmr_watch.log
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

resubmit() {
  sleep 60
  say "重提作业（上一次：$1）"
  bash "$PROJ/evolve/harness/scripts/submit_gpu_job.sh" "$WORKERS" "${SEEDS[@]}" >>"$LOG" 2>&1
  JOB="$(cat /tmp/fmr_last_job 2>/dev/null || echo "$JOB")"
  say "新作业：$JOB"
}

while true; do
  STATE="$(cd /tmp && timeout 120 rjob list 2>/dev/null | grep -E "rjob $JOB:" | tail -1)"
  case "$STATE" in
    *Succeeded*)
      say "✅ 作业完成：$JOB"
      # 找到最新的 sweep stem：先做离线判分（带 judge），再做收尾校验
      STEM="$(ls -t "$PROJ"/experiments/runs/sweep_dev_*_asb.json \
                   "$PROJ"/experiments/runs/sweep_dev_*_agentdojo.json \
                   "$PROJ"/experiments/runs/sweep_dev_*_agentharm.json \
                   "$PROJ"/experiments/runs/sweep_dev_*_autocontrol.json 2>/dev/null \
              | head -1 | sed -E 's/_(asb|agentdojo|agentharm|autocontrol)\.json$//')"
      if [ -n "${STEM:-}" ]; then
        say "离线判分（带 judge）：$STEM"
        ( cd "$PROJ" && env PYTHONPATH="evolve/harness/src:evolve/harness/scripts:evolve/harness/.pydeps:/mnt/shared-storage-user/ai4good1-share/majiachen/.fmr-pylibs" \
            python3 evolve/harness/scripts/rejudge_offline.py "$STEM" --workers 8 ) >>"$LOG" 2>&1
        say "收尾校验：$STEM"
        ( cd "$PROJ" && env PYTHONPATH="evolve/harness/src:evolve/harness/scripts:evolve/harness/.pydeps:/mnt/shared-storage-user/ai4good1-share/majiachen/.fmr-pylibs" \
            python3 evolve/harness/scripts/finalize_run.py "$STEM" ) >>"$LOG" 2>&1
        say "收尾校验完成（见 $LOG）"
      fi
      say "DONE"
      exit 0 ;;
    *Failed*|*Stopped*)
      say "❌ 作业 $JOB 状态=$STATE → 自动重提"
      resubmit "$STATE" ;;
    *)
      if tail -c 400 "$LOG" | grep -q "排队中"; then :; fi
      say "… $JOB 状态=$STATE"
      ;;
  esac
  sleep 300
done
