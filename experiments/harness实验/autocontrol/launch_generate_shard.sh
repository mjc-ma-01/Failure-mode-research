#!/usr/bin/env bash
set -euo pipefail

ROOT=/mnt/shared-storage-user/majiachen/Failure-mode-research
HERE="$ROOT/experiments/harness实验/autocontrol"
RUNNER="$HERE/run_eval_react.py"
MODEL=/mnt/shared-storage-gpfs2/gpfs2-shared-public/huggingface/hub/models--Qwen--Qwen3.5-9B/snapshots/c202236235762e1c871ad0ccb60c8ee5ba337b9a
REGISTRY="$HERE/tool_tier_registry.json"
PYTHON=/mnt/shared-storage-user/majiachen/safety-codesign/.venv/bin/python
SHARD_ID="${SHARD_ID:?set SHARD_ID 0..5}"
MANIFEST="$HERE/artifacts/generation_shards/shard_${SHARD_ID}.jsonl"
OUT="$HERE/runs/full/generation_shards/shard_${SHARD_ID}.jsonl"
LOG="$HERE/runs/full/generation_shards/shard_${SHARD_ID}.log"

export PYTHONPATH="$ROOT/evolve/harness/src${HARNESS_EXTRA_PYTHONPATH:+:$HARNESS_EXTRA_PYTHONPATH}${PYTHONPATH:+:$PYTHONPATH}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export PYTORCH_ALLOC_CONF=expandable_segments:True
export SAFEHARNESS_TOOL_TIER_TABLE="$REGISTRY"

mkdir -p "$(dirname "$OUT")"
exec > >(tee -a "$LOG") 2>&1
nvidia-smi
"$PYTHON" "$RUNNER" \
  --model "$MODEL" \
  --manifest "$MANIFEST" \
  --output "$OUT" \
  --conditions react,react+safeharness \
  --max-steps 8 \
  --max-new-tokens 4096 \
  --temperature 1.0 \
  --seed 42 \
  --resume
