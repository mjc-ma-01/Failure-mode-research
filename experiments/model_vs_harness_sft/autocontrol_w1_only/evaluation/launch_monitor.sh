#!/usr/bin/env bash
set -euo pipefail

ROOT=/mnt/shared-storage-user/majiachen/Failure-mode-research
HERE="$ROOT/experiments/model_vs_harness_sft/autocontrol_w1_only"
V2="$ROOT/experiments/model_vs_harness_sft/autocontrol_v2"
SHARED="$ROOT/experiments/model_vs_harness_sft/upward_deception/training"
MODEL=/mnt/shared-storage-gpfs2/gpfs2-shared-public/huggingface/hub/models--Qwen--Qwen3-32B/snapshots/30b8421510892303dc5ddd6cd0ac90ca2053478d
RUN="$HERE/evaluation/runs/t1_three_rollouts"
PYTHON=/mnt/shared-storage-user/majiachen/safety-codesign/.venv/bin/python
export PYTHONPATH="$SHARED/vendor_v1:$SHARED:$ROOT/evolve/harness/src:$ROOT/evolve/harness/scripts${PYTHONPATH:+:$PYTHONPATH}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export PYTORCH_ALLOC_CONF=expandable_segments:True

mkdir -p "$RUN/scored"
exec > >(tee -a "$RUN/scored/sft.log") 2>&1
nvidia-smi
"$PYTHON" "$V2/evaluation/score_monitor_local.py" \
  --trajectories "$RUN/sft.jsonl" --output "$RUN/scored/sft.jsonl" \
  --model "$MODEL" --batch-size 8 --max-new-tokens 1536
