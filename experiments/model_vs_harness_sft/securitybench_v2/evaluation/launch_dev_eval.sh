#!/usr/bin/env bash
set -euo pipefail

ROOT=/mnt/shared-storage-user/majiachen/Failure-mode-research
HERE="$ROOT/experiments/model_vs_harness_sft/securitybench_v2"
TRAIN="$HERE/training/runs/qwen35_9b_lora_v2_final"
MODEL=/mnt/shared-storage-gpfs2/gpfs2-shared-public/huggingface/hub/models--Qwen--Qwen3.5-9B/snapshots/c202236235762e1c871ad0ccb60c8ee5ba337b9a
PYTHON=/mnt/shared-storage-user/majiachen/safety-codesign/.venv/bin/python
OUTPUT="$HERE/evaluation/runs/dev_selection/trajectories.jsonl"
SOURCE="$ROOT/experiments/model_vs_harness_sft/upward_deception/training"
export PYTHONPATH="$SOURCE/vendor_v1:$SOURCE${PYTHONPATH:+:$PYTHONPATH}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export PYTORCH_ALLOC_CONF=expandable_segments:True

mkdir -p "$(dirname "$OUTPUT")"
test ! -e "$OUTPUT"
exec > >(tee -a "$HERE/evaluation/runs/dev_selection/generation.log") 2>&1
nvidia-smi
"$PYTHON" "$HERE/evaluation/run_eval.py" \
  --model "$MODEL" \
  --manifest "$HERE/evaluation/manifests/dev_selection.jsonl" \
  --output "$OUTPUT" \
  --include-base \
  --adapter "epoch1=$TRAIN/checkpoint-23" \
  --adapter "epoch2=$TRAIN/checkpoint-46" \
  --adapter "epoch3=$TRAIN/checkpoint-69" \
  --batch-size 16 --max-steps 6 --max-new-tokens 768 --seed 42
