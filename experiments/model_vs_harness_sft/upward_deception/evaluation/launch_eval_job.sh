#!/usr/bin/env bash
set -euo pipefail

ROOT=/mnt/shared-storage-user/majiachen/Failure-mode-research
EVAL_DIR="$ROOT/experiments/model_vs_harness_sft/upward_deception/evaluation"
TRAIN_DIR="$ROOT/experiments/model_vs_harness_sft/upward_deception/training"
MODEL=/mnt/shared-storage-gpfs2/gpfs2-shared-public/huggingface/hub/models--Qwen--Qwen3.5-9B/snapshots/c202236235762e1c871ad0ccb60c8ee5ba337b9a
ADAPTER="$TRAIN_DIR/runs/qwen35_9b_lora_v5/final_adapter"
TASKS="$ROOT/experiments/model_vs_harness_sft/upward_deception/output/split/test.jsonl"
FIXTURES="$ROOT/experiments/model_vs_harness_sft/upward_deception/output/fixtures"
RUN_NAME="${RUN_NAME:-paired_test_v1}"
OUTPUT="$EVAL_DIR/runs/$RUN_NAME"
PYTHON=/mnt/shared-storage-user/majiachen/safety-codesign/.venv/bin/python
export PYTHONPATH="$TRAIN_DIR/vendor_v1${PYTHONPATH:+:$PYTHONPATH}"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export PYTORCH_ALLOC_CONF=expandable_segments:True

mkdir -p "$OUTPUT"
exec > >(tee -a "$OUTPUT/job.log") 2>&1
echo "started_at=$(date --iso-8601=seconds)"
nvidia-smi
initial_memory_mib="$(
  nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits \
    | head -1 | tr -d ' '
)"
if (( initial_memory_mib > 2048 )); then
  echo "Refusing a busy GPU: initial memory is ${initial_memory_mib} MiB" >&2
  exit 75
fi

timeout --signal=TERM --kill-after=120s 6h \
  "$PYTHON" "$TRAIN_DIR/run_with_gpu_monitor.py" \
    --metrics "$OUTPUT/gpu_metrics.jsonl" \
    --summary "$OUTPUT/gpu_summary.json" \
    --interval 5 \
    --warmup-seconds 60 \
    -- \
    "$PYTHON" "$EVAL_DIR/run_local_eval.py" \
      --model "$MODEL" \
      --adapter "$ADAPTER" \
      --tasks "$TASKS" \
      --fixtures "$FIXTURES" \
      --output "$OUTPUT/trajectories.jsonl" \
      --batch-size 8 \
      --max-steps 6 \
      --max-new-tokens 1536 \
      --seed 42
echo "finished_at=$(date --iso-8601=seconds)"
