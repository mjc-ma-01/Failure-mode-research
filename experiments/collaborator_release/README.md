# Collaborator release bundle

This directory is the upload-ready, integrity-checked handoff for the two core
project modules:

1. the formal SFT experiments;
2. the matched three-arm Harness experiment.

The SFT payload and the full AutoControl three-arm Harness panel are complete.
The SecurityBench three-arm slot is populated only when the token-fixed rerun
passes its lifecycle and judge audits; the builder never copies the known
wall-clock-TTL-contaminated result.

## Layout

```text
collaborator_release/
├── README.md
├── SETTING.json
├── MANIFEST.json
├── build_release.py
├── shared_code/
│   └── evolve/harness/...       # shared AutoControl monitor/parser changes
├── sft/
│   ├── autocontrol_w1_only/
│   ├── securitybench_v2/
│   └── upward_deception/
└── harness/
    ├── autocontrol/             # 2,160 full trajectory+Monitor records
    ├── code/                    # shared ReAct / no-LLM SafeHarness runtime
    └── securitybench_clean/     # clean judged panel when audit passes
```

Each SFT track contains:

- `docs/`: the frozen protocol, setting, status, and formal report;
- `code/`: data construction, training, evaluation, and analysis entry points;
- `training_data/`: the exact accepted JSONL, manifest, and tokenization/quality
  metadata;
- `evaluation/`: one canonical combined trajectory-plus-judge JSONL, summary,
  aggregate analysis, and curated cases.

The combined evaluation JSONL is deliberately used instead of copying both a
raw trajectory file and a second near-duplicate judged file:

- AutoControl: `three_arm.jsonl` contains full messages, steps, and Monitor
  verdicts for 432 records;
- SecurityBench v2: `judged.jsonl` contains full messages/events and semantic
  judge outputs for 1,120 records;
- Upward Deception: `judged_records.jsonl` contains full messages/events and
  official/evidence/utility judge outputs for 240 records.

## Formal SFT scope

- `autocontrol_w1_only`: W1 complete-reference supervision only; Capability
  Misuse and W2 are excluded.
- `securitybench_v2`: W1 visible prompt conflict, W2 visible evidence state,
  and H1 hidden-provenance diagnostic.
- `upward_deception`: matched failure/success/authorized-fallback supervision.

Historical `autocontrol_v2`, SecurityBench v1, bridge/cross-fit, smoke,
interrupted, and `previous/` results are not copied.

## Three-arm Harness scope

The formal arms are `M`, `M+H`, and `M+H+ΔH`. AutoControl's canonical
`three_arm_scored.jsonl` contains 2,160 complete records (720/arm), including
messages or action steps and the full Qwen3-32B Monitor response. Because the
frozen `M` records serialize action/observation steps but not the initial
message array, `evaluation/task_specs/` also contains the exact 240 referenced
task specifications and an index mapping each original `spec_path` to its
release path. SecurityBench
uses a single combined `judged.jsonl`: every row contains the task, injection,
tool specifications, executed/blocked events, messages, final answer, and the
complete `deepseek-v4-pro-0813` semantic verdict.

## SecurityBench token-lifecycle audit

The old SecurityBench `M+H+ΔH` generation issued capability tokens before
queued GPU generation and contaminated 90 episodes through wall-clock expiry.
It is excluded. The uploaded panel is the clean rerun in which every generation
batch constructs its `Episode` and `SecurityPipeline` immediately before use:
600/600 ΔH cells, zero expired-token events, zero infrastructure runner errors,
and 1,800/1,800 complete DeepSeek verdicts. The builder only copies this panel
when its canonical manifest reports `complete_clean`.

## Build and verify

From the repository root:

```bash
python experiments/collaborator_release/build_release.py
python -m json.tool experiments/collaborator_release/SETTING.json >/dev/null
python -m json.tool experiments/collaborator_release/MANIFEST.json >/dev/null
```

`build_release.py` uses an explicit source whitelist. It rejects checkpoints,
optimizer state, adapters, logs, partial files, previous/invalid/smoke paths,
oversized files, and strings that resemble plaintext API keys. It never reads
`.env`, Codex configuration, or user home credentials.

`MANIFEST.json` records the source path, byte count, and SHA-256 for every
uploaded file. Regenerate it after any accepted clean Harness result is added.
