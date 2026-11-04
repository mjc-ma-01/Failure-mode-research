#!/usr/bin/env bash
# 自适应启动推理服务：venv-vLLM → 系统 vLLM → transformers 兜底（微批处理）。
# 用法：bash start_server.sh <port> <log>
set -uo pipefail
PORT="${1:-8000}"; LOG="${2:-/tmp/server.log}"
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
VENV_PY=/mnt/shared-storage-user/ai4good1-share/majiachen/.venvs/fmr-vllm/bin/python
CKPT=/mnt/shared-storage-gpfs2/gpfs2-shared-public/huggingface/hub/models--Qwen--Qwen3.5-9B
REV=c202236235762e1c871ad0ccb60c8ee5ba337b9a
MODEL_DIR="$CKPT/snapshots/$REV"

echo "[start_server] 探测可用后端…" | tee -a "$LOG"
{
  echo "[probe] python3: $(command -v python3) $(python3 -V 2>&1)"
  echo "[probe] torch: $(python3 -c 'import torch;print(torch.__version__, torch.cuda.is_available())' 2>&1 | tail -1)"
  echo "[probe] vllm(system): $(python3 -c 'import vllm;print(vllm.__version__)' 2>&1 | tail -1)"
  echo "[probe] vllm(venv): $("$VENV_PY" -c 'import vllm;print(vllm.__version__)' 2>&1 | tail -1)"
  echo "[probe] cuda libs: $(ls /usr/local/cuda*/lib64/libcudart.so* 2>/dev/null | head -2 | tr '\n' ' ')"
} >> "$LOG" 2>&1

if "$VENV_PY" -c "import vllm, torch; torch.zeros(1, device='cuda')" >/dev/null 2>&1; then
  echo "[start_server] 用 venv 的 vLLM" | tee -a "$LOG"
  exec bash "$ROOT/evolve/harness/scripts/serve_vllm.sh" "$PORT"
fi
if python3 -c "import vllm, torch; torch.zeros(1, device='cuda')" >/dev/null 2>&1; then
  echo "[start_server] 用系统 vLLM" | tee -a "$LOG"
  exec python3 -m vllm.entrypoints.openai.api_server --model "$MODEL_DIR" \
       --served-model-name qwen3.5-9b --host 127.0.0.1 --port "$PORT" \
       --dtype bfloat16 --max-model-len 32768 --gpu-memory-utilization 0.90 \
       --max-num-seqs 64 --trust-remote-code
fi
echo "[start_server] vLLM 不可用 → 尝试 transformers 兜底（优先容器自带 python）" | tee -a "$LOG"
PREBUILT_PYLIBS=/mnt/shared-storage-user/ai4good1-share/majiachen/.fmr-pylibs   # 登录节点预装（含 transformers 5.17）
RUN_DIR="/mnt/shared-storage-user/ai4good1-share/majiachen/Failure-mode-research/experiments/runs/_pylibs"
if python3 -c "import torch; torch.zeros(1, device='cuda')" >/dev/null 2>&1; then
  if PYTHONPATH="$PREBUILT_PYLIBS" python3 -c "from transformers.models.auto.configuration_auto import CONFIG_MAPPING; CONFIG_MAPPING['qwen3_5']" >/dev/null 2>&1; then
    RUN_DIR="$PREBUILT_PYLIBS"
    echo "[start_server] 使用预装 pylibs（登录节点已备好 transformers 5.17）" | tee -a "$LOG"
  elif ! python3 -c "import transformers; from transformers.models.auto.configuration_auto import CONFIG_MAPPING; CONFIG_MAPPING['qwen3_5']" >/dev/null 2>&1; then
    echo "[start_server] 容器 transformers 不认 qwen3_5 → 装新 transformers 到 job 本地目录（不动 torch）" | tee -a "$LOG"
    mkdir -p "$RUN_DIR"
    PIP_CACHE_DIR=/tmp/pip-cache python3 -m pip install -q --target "$RUN_DIR" \
      "transformers==5.17.0" "tokenizers>=0.23" 2>&1 | tail -3 | tee -a "$LOG" || true
  fi
  echo "[start_server] 用容器 python 的 transformers" | tee -a "$LOG"
  exec env PYTHONPATH="$RUN_DIR" python3 "$ROOT/evolve/harness/scripts/serve_transformers.py" \
       --port "$PORT" --ckpt "$MODEL_DIR" --max-batch 24 --max-new-tokens 256
fi
echo "[start_server] 用 venv python 的 transformers" | tee -a "$LOG"
exec "$VENV_PY" "$ROOT/evolve/harness/scripts/serve_transformers.py" \
     --port "$PORT" --ckpt "$MODEL_DIR" --max-batch 24 --max-new-tokens 256
