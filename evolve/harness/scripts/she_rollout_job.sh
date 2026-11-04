#!/usr/bin/env bash
# SHE 搜索台的 rollout 作业：起服务 → 标定 → 按 manifest 跑各 variant 的 rollout → 关服务。
# 用法（由 she_orchestrator 提交，经 FMR_SHE_MANIFEST 传 manifest 路径）：
#   bash she_rollout_job.sh [端口] [workers] [max_tokens]
set -euo pipefail
PORT="${1:-8000}"; shift || true
WORKERS="${1:-32}"; shift || true
MAXTOK="${1:-512}"; shift || true
[ "${MAXTOK:-0}" -ge 64 ] 2>/dev/null || MAXTOK=512      # 容错：占位传参 0/空 → 用默认

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
PY="${FMR_PY:-/mnt/shared-storage-user/ai4good1-share/majiachen/.venvs/fmr-vllm/bin/python}"
OUT_DIR="$ROOT/experiments/runs"
MANIFEST="${FMR_SHE_MANIFEST:?需要 FMR_SHE_MANIFEST 指向 manifest json}"
mkdir -p "$OUT_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
SERVER_LOG="$OUT_DIR/vllm_she_$STAMP.log"

echo "[she-job] 开始 $STAMP manifest=$MANIFEST"
bash "$ROOT/evolve/harness/scripts/start_server.sh" "$PORT" "$SERVER_LOG" > "$SERVER_LOG" 2>&1 &
SERVER_PID=$!
cleanup() { echo "[she-job] 关闭服务 pid=$SERVER_PID"; kill "$SERVER_PID" 2>/dev/null || true; wait "$SERVER_PID" 2>/dev/null || true; }
trap cleanup EXIT

for i in $(seq 1 48); do
  curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && { echo "[she-job] 服务就绪（${i}0s 内）"; break; }
  sleep 10
  [ "$i" = 48 ] && { echo "[she-job] 服务 8 分钟未就绪 → 退出" >&2; tail -30 "$SERVER_LOG" >&2; exit 1; }
done

"$PY" "$ROOT/evolve/harness/scripts/calibrate_util.py" \
  --base-url "http://127.0.0.1:$PORT" --model qwen3.5-9b \
  --concurrency 8 16 32 --seconds 45 --warmup 5 --prompt-tokens 2500 --max-tokens 256 \
  --target-util 0.50 --out "$OUT_DIR/calib_she_$STAMP.json" || echo "[she-job] 标定未达标（见上表）"

"$PY" "$ROOT/evolve/harness/scripts/she_rollout.py" \
  --manifest "$MANIFEST" --base-url "http://127.0.0.1:$PORT" \
  --workers "$WORKERS" --max-tokens "$MAXTOK"

echo "[she-job] 完成 $STAMP"
