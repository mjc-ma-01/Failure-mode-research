#!/usr/bin/env bash
set -eo pipefail

ROOT=/mnt/shared-storage-user/majiachen/Failure-mode-research
HERE="$ROOT/experiments/harness实验/securitybench/semantic_eval"
PYTHON=/mnt/shared-storage-user/majiachen/safety-codesign/.venv/bin/python

: "${OPENAI_API_KEY:?OPENAI_API_KEY must be set}"
: "${OPENAI_BASE_URL:?OPENAI_BASE_URL must be set to an endpoint supporting deepseek-v4-pro-0813}"

"$PYTHON" "$HERE/judge_trajectories.py" \
  --input "$HERE/judge_input.jsonl" \
  --output-dir "$HERE/results" \
  --workers "${JUDGE_WORKERS:-12}" \
  --request-profile "${JUDGE_REQUEST_PROFILE:-reasoning_low_json}" \
  --max-tokens "${JUDGE_MAX_TOKENS:-6000}"

"$PYTHON" "$HERE/analyze.py" \
  --input "$HERE/results/judged.jsonl" \
  --out-dir "$HERE/results"
