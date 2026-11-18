#!/usr/bin/env bash
set -euo pipefail

ROOT=/mnt/shared-storage-user/majiachen/Failure-mode-research
HERE="$ROOT/experiments/model_vs_harness_sft/autocontrol_w1_only"
SHARED="$ROOT/experiments/model_vs_harness_sft/upward_deception/training"
DATA="$HERE/data/train.jsonl"
MODEL=/mnt/shared-storage-gpfs2/gpfs2-shared-public/huggingface/hub/models--Qwen--Qwen3.5-9B/snapshots/c202236235762e1c871ad0ccb60c8ee5ba337b9a
RUN_NAME="${RUN_NAME:-qwen35_9b_lora_w1_only_sixcat}"
OUT="$HERE/training/runs/$RUN_NAME"
PYTHON=/mnt/shared-storage-user/majiachen/safety-codesign/.venv/bin/python
export PYTHONPATH="$SHARED/vendor_v1:$SHARED${PYTHONPATH:+:$PYTHONPATH}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export PYTORCH_ALLOC_CONF=expandable_segments:True

mkdir -p "$OUT"
exec > >(tee -a "$OUT/job.log") 2>&1
test ! -e "$OUT/final_adapter"
echo "started_at=$(date --iso-8601=seconds)"
nvidia-smi

"$PYTHON" "$HERE/build_dataset.py"
"$PYTHON" "$HERE/validate_tokenization.py" \
  --model "$MODEL" --data "$DATA" --max-length 4096 \
  --report "$OUT/tokenization_report.json"

timeout --signal=TERM --kill-after=120s 8h \
  "$PYTHON" "$SHARED/run_with_gpu_monitor.py" \
    --metrics "$OUT/gpu_metrics.jsonl" \
    --summary "$OUT/gpu_summary.json" \
    --interval 5 --warmup-seconds 30 -- \
    "$PYTHON" "$SHARED/train.py" \
      --model "$MODEL" --data "$DATA" --output-dir "$OUT" \
      --max-length 4096 --epochs 3 --learning-rate 7e-5 \
      --micro-batch-size 8 --gradient-accumulation-steps 2 \
      --num-workers 4 --seed 42

"$PYTHON" "$ROOT/experiments/model_vs_harness_sft/autocontrol_bridge/select_epoch_one_checkpoint.py" \
  --run-dir "$OUT"
echo "finished_at=$(date --iso-8601=seconds)"
