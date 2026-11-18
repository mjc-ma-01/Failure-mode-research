# Formal SFT experiments

This directory contains the model-weights side of the project question:

> For long-horizon LLM agents, which failure features are better addressed by
> supervised weight updates, and which require a runtime harness?

Only the three tracks below are formal SFT experiments. A lower risk rate is
not sufficient evidence of improvement: every track also measures task utility,
uses held-out tasks or scenarios, and retains paired trajectory evidence.

## Canonical tracks

| Track | Model-side target | Training data | Frozen evaluation | Formal result |
|---|---|---:|---:|---|
| `autocontrol_w1_only/` | Visible long-horizon policy choice | 140 trajectories from 35 scenarios | 12 held-out scenarios, 48 variants, 3 rollouts; 144 episodes/arm | Negative weights result: risk and utility both degrade |
| `securitybench_v2/` | Visible prompt-source conflict and evidence-state calibration | 364 trajectories | 1,120 trajectories across W1/W2/H1 | Strong W1/W2 weights gains; hidden provenance requires harness |
| `upward_deception/` | Evidence failure disclosure, source attribution, and grounded completion | 330 trajectories from 110 matched three-state tasks | 40 held-out tasks x 3 states x 2 arms = 240 trajectories | Evidence and utility improve without blanket refusal |

The machine-readable frozen setting and artifact hashes are in
[`SETTING.json`](SETTING.json).

## 1. AutoControl W1-only

Canonical directory: [`autocontrol_w1_only/`](autocontrol_w1_only/)

- Base model: `Qwen/Qwen3.5-9B`, fixed snapshot.
- Scope: Instrumental Convergence, Oversight Evasion, Specification Gaming,
  Covert Whistleblowing, Evaluation Awareness, and Strategic Misalignment.
- `Capability Misuse` is excluded from training, evaluation, aggregation, and
  claims.
- Training uses W1 complete-reference trajectories only. W2 state-calibration,
  tool-denial, partial/failure targets, and benign-control targets are excluded.
- LoRA: rank 16, alpha 32, dropout 0.05, three epochs; assistant-token-only
  cross-entropy.
- Evaluation: Base, W1-only SFT, and Base + SafeHarness adapted no-LLM on the
  same 144 cells/arm; temperature 1.0, three rollouts, eight steps.
- Judge: local `Qwen/Qwen3-32B` AutoControl action Monitor at temperature 0.

Formal result (`risk / task-success utility / safe task success` overall):

- Base: `30.6% / 61.8% / 39.6%`.
- W1-only SFT: `47.2% / 48.6% / 29.9%`.
- Base + Harness: `16.0% / 37.5% / 32.6%`.

This is a negative SFT result. W1-only supervision did not yield a reliable
long-horizon policy improvement and cannot be presented as a safety gain.

Primary files:

- `autocontrol_w1_only/PROTOCOL.md`
- `autocontrol_w1_only/SETTING.json`
- `autocontrol_w1_only/data/train.jsonl`
- `autocontrol_w1_only/evaluation/runs/t1_three_rollouts/analysis/REPORT.md`
- `autocontrol_w1_only/evaluation/runs/t1_three_rollouts/analysis/INSIGHTS_CN.md`

## 2. SecurityBench v2

Canonical directory: [`securitybench_v2/`](securitybench_v2/)

This is an AgentSecurityBench-derived causal diagnostic, not a reproduction of
the benchmark leaderboard. It separates three information regimes:

- W1: the prompt-source conflict is visible to the model;
- W2: success, partial, failure, or missing-input evidence is visible;
- H1: trusted versus substituted tool provenance differs only in a
  model-invisible implementation HMAC.

Training uses 364 trajectories from 13 training tasks and 52 variants. The
model is `Qwen/Qwen3.5-9B` with rank-16 LoRA for three epochs. Test agents,
tasks, normal tools, and attack tools are disjoint from training. The frozen
checkpoint is `checkpoint-69`, selected using dev only.

Formal findings:

- W1 attack side effects: Base `69.2%` -> SFT `1.3%`; original-task utility:
  `19.6%` -> `94.6%`.
- W2 calibrated utility: Base `34.4%` -> SFT `76.9%`.
- In H1 substituted twins, SFT alone executes the hidden replacement in
  `100%` of cases and has `0%` utility; provenance verification changes this
  to `0%` side effects and `100%` utility while preserving trusted-cell
  utility.

The weights conclusion applies to model-visible instruction and evidence
states. The H1 conclusion applies to model-invisible provenance and therefore
requires a harness.

Primary files:

- `securitybench_v2/PROTOCOL.md`
- `securitybench_v2/RESULTS_CN.md`
- `securitybench_v2/RUN_MANIFEST.json`
- `securitybench_v2/output/sft/train.jsonl`
- `securitybench_v2/evaluation/runs/frozen_test/analysis.json`
- `securitybench_v2/evaluation/runs/frozen_test/CASES.md`

## 3. Upward Deception

Canonical directory: [`upward_deception/`](upward_deception/)

The target is narrow: when required evidence is missing, broken, irrelevant,
or replaced, the model must disclose that state rather than fabricate
completion. Each accepted training task has three replayed counterfactuals:

- `failure`: disclose unavailable/insufficient evidence;
- `success`: use sufficient primary evidence and complete the task;
- `authorized_fallback`: use an explicitly authorized cache and disclose the
  actual source.

The dataset contains 330 accepted trajectories from 110 matched task triples.
`glm-5.3` generates offline candidates; deterministic replay, the official
failure rubric, and independent evidence/utility reviews gate inclusion. Only
assistant tokens receive loss.

Frozen evaluation uses 40 held-out official tasks, all three states, Base and
SFT, temperature 0, one rollout, and no runtime harness.

Formal findings:

- Failure official risky rate: `22.5%` -> `7.5%`.
- Failure evidence pass: `45.0%` -> `77.5%`.
- Failure utility pass: `57.5%` -> `90.0%`.
- Success utility: `70.0%` -> `100.0%`.
- Authorized-fallback evidence-and-utility: `65.0%` -> `87.5%`.
- Over-refusal remains `0/40` in every state for both arms.

Primary files:

- `upward_deception/PROTOCOL.md`
- `upward_deception/output/sft/train.jsonl`
- `upward_deception/evaluation/EVAL_PROTOCOL.md`
- `upward_deception/evaluation/runs/paired_test_v2_clean/REPORT_ZH.md`
- `upward_deception/evaluation/runs/paired_test_v2_clean/analysis/analysis.json`

## Non-formal and historical directories

The following directories are not part of the formal SFT result and must not
be merged into its tables or claims:

- `autocontrol_v2/`: historical mixed W1+W2 supervision; superseded by the
  frozen W1-only directive for AutoControl.
- `securitybench/`: v1 experiment; superseded by `securitybench_v2/`.
- `autocontrol_bridge/`: earlier bridge, temperature ablations, and a paused
  cross-fit diagnostic; not a formal SFT track.
- `react_base_harness/`: Harness infrastructure/history, not an SFT track.
- `NEXT_REACT_BASE_HARNESS_TASK.md`: historical handoff note.

The separate three-arm Harness experiment is maintained under
`experiments/harness实验/` and is deliberately outside this module.

## Repository artifact policy

Commit source code, protocols, frozen manifests, accepted training JSONL files,
hashes, aggregate analyses, curated cases, and one canonical combined
trajectory-plus-judge record per formal evaluation in
`experiments/collaborator_release/`. Do not commit:

- `training/runs/`, checkpoints, optimizer state, or adapter binaries;
- `checkpoint-*`, `final_adapter/`, `*.pt`, or `*.safetensors`;
- `__pycache__/`, `*.pyc`, logs, or GPU telemetry;
- interrupted, invalid, smoke, partial, or `previous/` outputs;
- redundant raw trajectories when the combined judged record already embeds
  the full task, messages/events, final answer, and judge output.

Large model artifacts belong in external artifact storage. The repository
records their SHA-256 and the selected-checkpoint metadata needed to retrieve
and verify them.
