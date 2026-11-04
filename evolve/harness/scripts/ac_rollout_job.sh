#!/usr/bin/env bash
# AutoControl rollout 作业：起服务 → 标定 → ac_rollout.py → 关服务。
set -euo pipefail
PORT="${1:-8000}"; shift || true
WORKERS="${1:-24}"; shift || true
MAXTOK="${1:-512}"; shift || true
[ "${MAXTOK:-0}" -ge 64 ] 2>/dev/null || MAXTOK=512
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
PY="${FMR_PY:-/mnt/shared-storage-user/ai4good1-share/majiachen/.venvs/fmr-vllm/bin/python}"
OUT_DIR="$ROOT/experiments/runs"; mkdir -p "$OUT_DIR"
MANIFEST="${FMR_SHE_MANIFEST:?需要 FMR_SHE_MANIFEST}"
STAMP="$(date +%Y%m%d-%H%M%S)"
SERVER_LOG="$OUT_DIR/vllm_ac_$STAMP.log"
echo "[ac-job] 开始 $STAMP manifest=$MANIFEST"
bash "$ROOT/evolve/harness/scripts/start_server.sh" "$PORT" "$SERVER_LOG" > "$SERVER_LOG" 2>&1 &
SERVER_PID=$!
cleanup() { kill "$SERVER_PID" 2>/dev/null || true; wait "$SERVER_PID" 2>/dev/null || true; }
trap cleanup EXIT
for i in $(seq 1 48); do
  curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && { echo "[ac-job] 服务就绪"; break; }
  sleep 10
  [ "$i" = 48 ] && { echo "[ac-job] 服务未就绪 → 退出" >&2; tail -30 "$SERVER_LOG" >&2; exit 1; }
done
"$PY" "$ROOT/evolve/harness/scripts/calibrate_util.py" \
  --base-url "http://127.0.0.1:$PORT" --model qwen3.5-9b \
  --concurrency 8 16 24 --seconds 45 --warmup 5 --prompt-tokens 2500 --max-tokens 256 \
  --target-util 0.50 --out "$OUT_DIR/calib_ac_$STAMP.json" || echo "[ac-job] 标定未达标"
"$PY" "$ROOT/evolve/harness/scripts/ac_rollout.py" \
  --manifest "$MANIFEST" --base-url "http://127.0.0.1:$PORT" --workers "$WORKERS" --max-tokens "$MAXTOK"
echo "[ac-job] 完成 $STAMP"
