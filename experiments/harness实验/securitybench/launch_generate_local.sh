#!/usr/bin/env bash
set -euo pipefail

ROOT=/mnt/shared-storage-user/majiachen/Failure-mode-research
HERE="$ROOT/experiments/harness实验/securitybench"
PYTHON="${HARNESS_PYTHON:-/mnt/shared-storage-user/majiachen/safety-codesign/.venv/bin/python}"
MODEL="${HARNESS_MODEL_PATH:-/mnt/shared-storage-gpfs2/gpfs2-shared-public/huggingface/hub/models--Qwen--Qwen3.5-9B/snapshots/c202236235762e1c871ad0ccb60c8ee5ba337b9a}"
OUT="${ASB_OUTPUT:-$HERE/raw/react_arms_token_fixed.jsonl}"
CONDITIONS="${ASB_CONDITIONS:-react,react+safeharness}"
METHODS="${ASB_METHODS:-DPI,OPI}"
ATTACK_TYPES="${ASB_ATTACK_TYPES:-naive,context_ignoring,fake_completion}"
BATCH_SIZE="${ASB_BATCH_SIZE:-12}"

mkdir -p "$(dirname "$OUT")"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export PYTHONPATH="$ROOT/evolve/harness/src${HARNESS_EXTRA_PYTHONPATH:+:$HARNESS_EXTRA_PYTHONPATH}${PYTHONPATH:+:$PYTHONPATH}"

"$PYTHON" "$HERE/run_eval_react_local.py" \
  --out "$OUT" \
  --model "$MODEL" \
  --tier-table "$HERE/asb_tier_table_5agents_principled.json" \
  --conditions "$CONDITIONS" \
  --methods "$METHODS" \
  --attack-types "$ATTACK_TYPES" \
  --tasks-per-agent 1 \
  --tools-per-agent 20 \
  --seeds 0 \
  --max-steps 4 \
  --sample-seed 20261022 \
  --batch-size "$BATCH_SIZE" \
  --resume
