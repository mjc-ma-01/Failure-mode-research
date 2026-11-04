#!/usr/bin/env bash
# 常驻 vLLM 服务：一张卡 serve Qwen3.5-9B，供并发 episode 客户端调用。
#
# 用法：bash evolve/harness/scripts/serve_vllm.sh [端口]
# 注意：先用 `python -c "import vllm; print(vllm.__version__)"` 确认该版本支持 qwen3_5 架构。
set -euo pipefail

PORT="${1:-8000}"
CKPT=/mnt/shared-storage-gpfs2/gpfs2-shared-public/huggingface/hub/models--Qwen--Qwen3.5-9B
REV=c202236235762e1c871ad0ccb60c8ee5ba337b9a
MODEL_DIR="$CKPT/snapshots/$REV"
PY="${FMR_PY:-/mnt/shared-storage-user/ai4good1-share/majiachen/.venvs/fmr-vllm/bin/python}"

export HF_HUB_OFFLINE=1
export VLLM_LOGGING_LEVEL=INFO

exec "$PY" -m vllm.entrypoints.openai.api_server \
  --model "$MODEL_DIR" \
  --served-model-name qwen3.5-9b \
  --revision "$REV" \
  --host 127.0.0.1 --port "$PORT" \
  --dtype bfloat16 \
  --max-model-len 32768 \
  --gpu-memory-utilization 0.90 \
  --max-num-seqs 64 \
  --enable-prefix-caching \
  --trust-remote-code

# 参数说明（与利用率直接相关）：
#   --max-num-seqs 64        允许同时跑的序列数 → 连续批处理的关键
#   --enable-prefix-caching  episode 每一步共享同一前缀（任务 + 历史）→ 省算力、提吞吐
#   --gpu-memory-utilization 留给 KV cache 的显存比例；
#       本模型 32 层里只有 8 层全注意力且 num_kv_heads=4/head_dim=256，
#       每 token KV 约 32KB → 100k tokens 也才约 3GB，够开很大并发。
