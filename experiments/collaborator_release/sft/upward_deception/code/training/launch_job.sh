#!/usr/bin/env bash
set -euo pipefail

ROOT=/mnt/shared-storage-user/majiachen/Failure-mode-research
TRAINING_DIR="$ROOT/experiments/model_vs_harness_sft/upward_deception/training"
DATA="$ROOT/experiments/model_vs_harness_sft/upward_deception/output/sft/train.jsonl"
MODEL=/mnt/shared-storage-gpfs2/gpfs2-shared-public/huggingface/hub/models--Qwen--Qwen3.5-9B/snapshots/c202236235762e1c871ad0ccb60c8ee5ba337b9a
RUN_NAME="${RUN_NAME:-qwen35_9b_lora_v1}"
OUTPUT_DIR="$TRAINING_DIR/runs/$RUN_NAME"
PYTHON=/mnt/shared-storage-user/majiachen/safety-codesign/.venv/bin/python
export PYTHONPATH="$TRAINING_DIR/vendor_v1${PYTHONPATH:+:$PYTHONPATH}"

mkdir -p "$OUTPUT_DIR"
exec > >(tee -a "$OUTPUT_DIR/job.log") 2>&1
echo "started_at=$(date --iso-8601=seconds)"
echo "hostname=$(hostname)"
nvidia-smi
initial_memory_mib="$(
  nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits \
    | head -1 | tr -d ' '
)"
if (( initial_memory_mib > 2048 )); then
  echo "Refusing a busy GPU: initial memory is ${initial_memory_mib} MiB" >&2
  exit 75
fi

"$PYTHON" - <<'PY'
import accelerate
import peft
import torch
import transformers

assert torch.cuda.is_available()
assert transformers.__version__ == "5.8.1"
assert peft.__version__ == "0.21.2"
print(
    {
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "peft": peft.__version__,
        "accelerate": accelerate.__version__,
        "gpu": torch.cuda.get_device_name(0),
        "bf16": torch.cuda.is_bf16_supported(),
    },
    flush=True,
)
assert torch.cuda.is_bf16_supported()
PY
"$PYTHON" - <<'PY' > "$OUTPUT_DIR/runtime_versions.json"
import json
import accelerate
import huggingface_hub
import peft
import torch
import transformers

print(json.dumps({
    "torch": torch.__version__,
    "cuda_build": torch.version.cuda,
    "transformers": transformers.__version__,
    "peft": peft.__version__,
    "accelerate": accelerate.__version__,
    "huggingface_hub": huggingface_hub.__version__,
}, indent=2))
PY

"$PYTHON" "$TRAINING_DIR/dry_run.py" \
  --model "$MODEL" \
  --data "$DATA" \
  --max-length 8192 \
  --report "$OUTPUT_DIR/tokenization_report.json"

export TOKENIZERS_PARALLELISM=true
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

timeout --signal=TERM --kill-after=120s 8h \
  "$PYTHON" "$TRAINING_DIR/run_with_gpu_monitor.py" \
    --metrics "$OUTPUT_DIR/gpu_metrics.jsonl" \
    --summary "$OUTPUT_DIR/gpu_summary.json" \
    --interval 5 \
    --warmup-seconds 120 \
    -- \
    "$PYTHON" "$TRAINING_DIR/train.py" \
      --model "$MODEL" \
      --data "$DATA" \
      --output-dir "$OUTPUT_DIR" \
      --max-length 8192 \
      --epochs 3 \
      --learning-rate 1e-4 \
      --micro-batch-size 4 \
      --gradient-accumulation-steps 4 \
      --num-workers 4 \
      --seed 42

echo "finished_at=$(date --iso-8601=seconds)"
