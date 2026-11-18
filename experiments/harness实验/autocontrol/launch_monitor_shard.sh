#!/usr/bin/env bash
set -euo pipefail

ROOT=/mnt/shared-storage-user/majiachen/Failure-mode-research
HERE="$ROOT/experiments/harness实验/autocontrol"
MODEL=/mnt/shared-storage-gpfs2/gpfs2-shared-public/huggingface/hub/models--Qwen--Qwen3-32B/snapshots/30b8421510892303dc5ddd6cd0ac90ca2053478d
PYTHON=/mnt/shared-storage-user/majiachen/safety-codesign/.venv/bin/python
ARM_SLUG="${ARM_SLUG:?set ARM_SLUG to m, react, or react_safe}"
SHARD_ID="${SHARD_ID:?set SHARD_ID to 0..2}"
INPUT="$HERE/runs/full/monitor_inputs/${ARM_SLUG}_s${SHARD_ID}.jsonl"
OUTPUT="$HERE/runs/full/scored/shards/${ARM_SLUG}_s${SHARD_ID}.jsonl"
LOG="$HERE/runs/full/scored/shards/${ARM_SLUG}_s${SHARD_ID}.log"

export PYTHONPATH="$ROOT/evolve/harness/src:$ROOT/evolve/harness/scripts${HARNESS_EXTRA_PYTHONPATH:+:$HARNESS_EXTRA_PYTHONPATH}${PYTHONPATH:+:$PYTHONPATH}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export PYTORCH_ALLOC_CONF=expandable_segments:True
mkdir -p "$(dirname "$OUTPUT")"
exec > >(tee -a "$LOG") 2>&1
nvidia-smi
"$PYTHON" "$HERE/score_monitor_local.py" \
  --trajectories "$INPUT" \
  --output "$OUTPUT" \
  --model "$MODEL" \
  --batch-size 8 \
  --max-new-tokens 1536
