#!/usr/bin/env bash
# AgentDojo 搜索台作业：起服务 → 跑进化循环（rollout/提案/门控/fresh anchor）→ heldout → 关服务。
# 用法：bash run_agentdojo_evolution.sh [端口] [轮数] [种子...]
set -euo pipefail
PORT="${1:-8000}"; shift || true
ROUNDS="${1:-3}"; shift || true
SEEDS=("$@"); [ ${#SEEDS[@]} -eq 0 ] && SEEDS=(0)

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
PY="${FMR_PY:-/mnt/shared-storage-user/ai4good1-share/majiachen/.venvs/fmr-vllm/bin/python}"
OUT_DIR="$ROOT/experiments/runs"
WORKDIR="${FMR_EVOLVE_WORKDIR:-$ROOT/experiments/evolve_agentdojo_run_$(date +%m%d-%H%M)}"
mkdir -p "$OUT_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
SERVER_LOG="$OUT_DIR/vllm_$STAMP.log"

echo "[evolve] 作业开始 $STAMP rounds=$ROUNDS seeds=${SEEDS[*]} workdir=$WORKDIR"
bash "$ROOT/evolve/harness/scripts/start_server.sh" "$PORT" "$SERVER_LOG" > "$SERVER_LOG" 2>&1 &
SERVER_PID=$!
cleanup() { echo "[evolve] 关闭服务 pid=$SERVER_PID"; kill "$SERVER_PID" 2>/dev/null || true; wait "$SERVER_PID" 2>/dev/null || true; }
trap cleanup EXIT

for i in $(seq 1 48); do
  curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && { echo "[evolve] 服务就绪（${i}0s 内）"; break; }
  sleep 10
  [ "$i" = 48 ] && { echo "[evolve] 服务 8 分钟未就绪 → 退出" >&2; tail -30 "$SERVER_LOG" >&2; exit 1; }
done

"$PY" "$ROOT/evolve/harness/scripts/calibrate_util.py" \
  --base-url "http://127.0.0.1:$PORT" --model qwen3.5-9b \
  --concurrency 8 16 32 --seconds 45 --warmup 5 --prompt-tokens 2500 --max-tokens 256 \
  --target-util 0.50 --out "$OUT_DIR/calib_$STAMP.json" || echo "[evolve] 标定未达标（见上表）"

"$PY" "$ROOT/evolve/harness/scripts/evolve_agentdojo.py" \
  --rounds "$ROUNDS" --seeds "${SEEDS[@]}" --base-url "http://127.0.0.1:$PORT" \
  --workdir "$WORKDIR" --proposer "${FMR_PROPOSER:-claude-sonnet-4-6}"

echo "[evolve] 完成；日志 $WORKDIR/evolution_log.json"
