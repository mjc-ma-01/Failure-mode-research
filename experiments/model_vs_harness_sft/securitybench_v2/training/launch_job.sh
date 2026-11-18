#!/usr/bin/env bash
set -euo pipefail

ROOT=/mnt/shared-storage-user/majiachen/Failure-mode-research
SOURCE="$ROOT/experiments/model_vs_harness_sft/upward_deception/training"
HERE="$ROOT/experiments/model_vs_harness_sft/securitybench_v2/training"
DATA="$ROOT/experiments/model_vs_harness_sft/securitybench_v2/output/sft/train.jsonl"
MODEL=/mnt/shared-storage-gpfs2/gpfs2-shared-public/huggingface/hub/models--Qwen--Qwen3.5-9B/snapshots/c202236235762e1c871ad0ccb60c8ee5ba337b9a
RUN_NAME="${RUN_NAME:-qwen35_9b_lora_v2}"
OUT="$HERE/runs/$RUN_NAME"
PYTHON=/mnt/shared-storage-user/majiachen/safety-codesign/.venv/bin/python
export PYTHONPATH="$SOURCE/vendor_v1:$SOURCE${PYTHONPATH:+:$PYTHONPATH}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export PYTORCH_ALLOC_CONF=expandable_segments:True

mkdir -p "$OUT"
exec > >(tee -a "$OUT/job.log") 2>&1
test ! -e "$OUT/final_adapter"
echo "started_at=$(date --iso-8601=seconds)"
nvidia-smi

"$PYTHON" "$HERE/dry_run.py" \
  --model "$MODEL" --data "$DATA" --max-length 8192 \
  --report "$OUT/tokenization_report.json"

timeout --signal=TERM --kill-after=120s 8h \
  "$PYTHON" "$SOURCE/run_with_gpu_monitor.py" \
    --metrics "$OUT/gpu_metrics.jsonl" \
    --summary "$OUT/gpu_summary.json" \
    --interval 5 --warmup-seconds 60 -- \
    "$PYTHON" "$SOURCE/train.py" \
      --model "$MODEL" --data "$DATA" --output-dir "$OUT" \
      --max-length 8192 --epochs 3 --learning-rate 7e-5 \
      --micro-batch-size 4 --gradient-accumulation-steps 4 \
      --num-workers 4 --seed 42
echo "finished_at=$(date --iso-8601=seconds)"
