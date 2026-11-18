# Model-Side SFT: Upward Deception

This directory constructs replay-validated SFT trajectories for failure disclosure,
source attribution, and result fabrication.

The authoritative design is in [`PROTOCOL.md`](PROTOCOL.md).

## Models

- trajectory and fixture teacher: `glm-5.3`;
- official Upward outcome judge: `gpt-4o-mini`;
- evidence/authorization judge: `deepseek-v4-pro`;
- separate feasible-utility/over-refusal judge: `deepseek-v4-pro`;
- intended student: `Qwen/Qwen3.5-9B`.

## Commands

```bash
set -a
source ../../../data/AutoControl-Arena/.env
set +a

python build_gold_dataset.py prepare
python build_gold_dataset.py fixtures --workers 4
python build_gold_dataset.py trajectories --workers 4
python build_gold_dataset.py export
```

For a five-task calibration batch:

```bash
python build_gold_dataset.py fixtures --limit-per-type 1
python build_gold_dataset.py trajectories --limit-per-type 1
```

The primary training artifact is `output/sft/train.jsonl`. Rejected, missing, or
judge-disputed cells are listed in `output/review_queue.jsonl` and are excluded
from training.
