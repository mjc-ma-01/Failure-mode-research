#!/usr/bin/env bash
# 一次"短而密"的作业：作业内起 vLLM → 健康检查 → 功率标定 → 并发 sweep → 关服务 → 打印利用率结论。
#
# 实验室口径（硬性）：占用率 >75%、利用率 >50%（H200 上 50% ≈ 410W）。
# 因此本脚本：① 先做并发/功率标定（确认可持续达标）；② 用高并发跑 sweep（队列常满）。
#
# 形态依据见 docs/GPU_UTILIZATION.md：常驻服务会因长期空转被判低效，正式实验一律用
# 作业内起服务 + 并发池常满 + 跑完释放。
#
# 用法：
#   bash evolve/harness/scripts/run_sweep.sh [端口] [workers] [seeds...]
# 例：
#   bash evolve/harness/scripts/run_sweep.sh 8000 32 0 1 2
set -euo pipefail

PORT="${1:-8000}"; shift || true
WORKERS="${1:-32}"; shift || true
SEEDS=("$@"); [ ${#SEEDS[@]} -eq 0 ] && SEEDS=(0 1 2)

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
PY="${FMR_PY:-/mnt/shared-storage-user/ai4good1-share/majiachen/.venvs/fmr-vllm/bin/python}"
OUT_DIR="$ROOT/experiments/runs"
mkdir -p "$OUT_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
SERVER_LOG="$OUT_DIR/vllm_$STAMP.log"
REPORT="$OUT_DIR/sweep_dev_$STAMP.json"

echo "[sweep] 作业开始 $STAMP  端口=$PORT workers=$WORKERS seeds=${SEEDS[*]}"

# ---- 1) 作业内起服务 ----
bash "$ROOT/evolve/harness/scripts/start_server.sh" "$PORT" "$SERVER_LOG" > "$SERVER_LOG" 2>&1 &
SERVER_PID=$!
cleanup() {
  echo "[sweep] 关闭服务 pid=$SERVER_PID"
  kill "$SERVER_PID" 2>/dev/null || true
  wait "$SERVER_PID" 2>/dev/null || true
}
trap cleanup EXIT

echo "[sweep] 等待服务就绪（日志：$SERVER_LOG，最多 8 分钟）"
for i in $(seq 1 48); do
  if curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
    echo "[sweep] 服务就绪（${i}0s 内）"
    break
  fi
  sleep 10
  if [ "$i" = 48 ]; then
    echo "[sweep] 服务 8 分钟未就绪 → 退出，释放 GPU（不留空转）" >&2
    tail -30 "$SERVER_LOG" >&2
    exit 1
  fi
done

# ---- 2) 并发 sweep（含功率与队列采样）----
echo "[sweep] 开始 sweep"
CAL_JSON="$OUT_DIR/calib_$STAMP.json"
"$PY" "$ROOT/evolve/harness/scripts/calibrate_util.py" \
  --base-url "http://127.0.0.1:$PORT" --model qwen3.5-9b \
  --concurrency 8 16 32 --seconds 45 --warmup 5 --prompt-tokens 2500 --max-tokens 256 \
  --target-util 0.50 --out "$CAL_JSON" || echo "[sweep] 标定未达标（看上面的表）"
CHOSEN=$("$PY" -c "import json;print(json.load(open('$CAL_JSON')).get('chosen_concurrency') or '')" 2>/dev/null || true)
# 标定只用来"确认能达标"；真实负载比合成负载轻，所以并发**只升不降**
if [ -n "$CHOSEN" ] && [ "$CHOSEN" -gt "$WORKERS" ]; then WORKERS="$CHOSEN"; fi
echo "[sweep] 使用并发=$WORKERS（≥标定推荐；真实负载更轻，只升不降）"

# 各来源导入探针（1–2 格、不占 GPU 算力；把容器内的真实错误记进日志）
echo "[sweep] 各来源导入探针"
for SRC in asb agentdojo agentharm autocontrol; do
  case "$SRC" in
    asb)         EXTRA="--asb-cells 2"; ED="$ROOT/evolve/harness/configs/edits_v0.json" ;;
    agentdojo)   EXTRA="--agentdojo-users-map banking=1"; ED="$ROOT/evolve/harness/configs/edits_agentdojo.json" ;;
    agentharm)   EXTRA="--agentharm-cells 2"; ED="$ROOT/evolve/harness/configs/edits_agentharm.json" ;;
    autocontrol) EXTRA=""; ED="$ROOT/evolve/harness/configs/edits_autocontrol.json" ;;
  esac
  echo "[probe] --- $SRC ---"
  "$PY" "$ROOT/evolve/harness/scripts/run_pair_sweep.py" --model scripted --seeds 0 \
    $EXTRA --sources "$SRC" --edits "$ROOT/evolve/harness/configs/edits_core.json,$ED" 2>&1 | tail -3 || true
done

# 四来源全部跑一遍（格子多 → 队列更密 → 功率更容易达标）
for SRC in asb agentdojo agentharm autocontrol; do
  case "$SRC" in
    asb)        EXTRA="--asb-cells 70 --split dev"; ED="$ROOT/evolve/harness/configs/edits_v0.json" ;;
    agentdojo)  EXTRA="--agentdojo-users-map banking=3,slack=2,travel=2,workspace=2 --split dev"; ED="$ROOT/evolve/harness/configs/edits_agentdojo.json" ;;
    agentharm)  EXTRA="--agentharm-cells 70"; ED="$ROOT/evolve/harness/configs/edits_agentharm.json" ;;
    autocontrol) EXTRA=""; ED="$ROOT/evolve/harness/configs/edits_autocontrol.json" ;;
  esac
  echo "[sweep] --- 来源 $SRC ---"
  "$PY" "$ROOT/evolve/harness/scripts/run_pair_sweep.py" \
    --base-url "http://127.0.0.1:$PORT" --model qwen3.5-9b --max-tokens 512 \
    --workers "$WORKERS" --seeds "${SEEDS[@]}" $EXTRA --sources "$SRC" \
    --classify --edits "$ROOT/evolve/harness/configs/edits_core.json,$ED" \
    --out "${REPORT%.json}_$SRC.json" || echo "[sweep] 来源 $SRC 失败，继续下一个"
done

# ---- 3) 收尾（trap 会关服务）----
echo "[sweep] 作业结束；报告 $REPORT"
# 判定只看**任务完成度**（利用率只是运行时的调参信号，不进结果记录）
echo "[verdict] 任务完成度检查（按来源）："
DONE=0; FAIL=""
for SRC in asb agentdojo agentharm autocontrol; do
  F="${REPORT%.json}_${SRC}.json"
  if [ -s "$F" ]; then DONE=$((DONE+1)); echo "  ✅ $SRC → $F"; else FAIL="$FAIL $SRC"; echo "  ❌ $SRC 未产出报告"; fi
done
echo "[verdict] 完成 $DONE/4 个来源"
[ -z "$FAIL" ] || { echo "[verdict] 未完成来源:$FAIL（下轮据探针日志修复）"; exit 1; }
