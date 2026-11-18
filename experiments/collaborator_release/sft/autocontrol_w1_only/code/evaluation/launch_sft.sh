#!/usr/bin/env bash
set -euo pipefail

ROOT=/mnt/shared-storage-user/majiachen/Failure-mode-research
HERE="$ROOT/experiments/model_vs_harness_sft/autocontrol_w1_only"
V2="$ROOT/experiments/model_vs_harness_sft/autocontrol_v2"
BRIDGE="$ROOT/experiments/model_vs_harness_sft/autocontrol_bridge"
SHARED="$ROOT/experiments/model_vs_harness_sft/upward_deception/training"
MODEL=/mnt/shared-storage-gpfs2/gpfs2-shared-public/huggingface/hub/models--Qwen--Qwen3.5-9B/snapshots/c202236235762e1c871ad0ccb60c8ee5ba337b9a
RUN_DIR="$HERE/training/runs/qwen35_9b_lora_w1_only_sixcat"
ADAPTER="$RUN_DIR/final_adapter"
MANIFEST="$BRIDGE/artifacts/bridge_manifest.jsonl"
OUT="$HERE/evaluation/runs/t1_three_rollouts"
PYTHON=/mnt/shared-storage-user/majiachen/safety-codesign/.venv/bin/python
export PYTHONPATH="$SHARED/vendor_v1:$SHARED:$ROOT/evolve/harness/src${PYTHONPATH:+:$PYTHONPATH}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export PYTORCH_ALLOC_CONF=expandable_segments:True

test -f "$ADAPTER/adapter_model.safetensors"
mkdir -p "$OUT"
exec > >(tee -a "$OUT/generation_sft.log") 2>&1
nvidia-smi
"$PYTHON" "$V2/evaluation/run_eval.py" \
  --model "$MODEL" --manifest "$MANIFEST" --output "$OUT/sft.jsonl" \
  --adapter "sft=$ADAPTER" --resume --panels W1 --batch-size 1 \
  --max-steps 8 --max-new-tokens 4096 --seed 42 --temperature 1.0
echo "finished_at=$(date --iso-8601=seconds)"
