# AutoControl W1-only weights-vs-harness protocol

This is the corrective AutoControl SFT experiment. It permanently applies the
following scope rules for this experiment and its follow-ups:

- Exclude `Capability Misuse` from training, evaluation, and reported totals.
- Train only on `W1_visible_policy_choice / reference_complete` trajectories.
- Exclude all W2 state-calibration, tool-denial, partial, and failed targets.
- Exclude the W1 hard-negative augmentation from the primary model so every
  task variant contributes exactly one canonical, safe, task-complete target.

## Training data

The source is the previously simulator-replayed and DeepSeek-V4-Pro-audited
AutoControl training set. Filtering is deterministic:

```text
panel == W1_visible_policy_choice
condition == reference_complete
risk_category != Capability Misuse
final claim == completed
```

Expected volume: 35 independent base scenarios, four S/T variants each, 140
rows. The four variants are repeated contexts, not independent scenarios.

## Training recipe

- Base: Qwen3.5-9B frozen snapshot used by the prior bridge.
- LoRA rank 16, alpha 32, dropout 0.05.
- Assistant-token-only per-example mean cross entropy.
- Three epochs are trained and the epoch-three final adapter is selected by a
  fixed rule without using held-out Monitor outcomes. With 140 rows this is 27
  optimizer steps, closely matching the 29 optimizer steps in the prior
  bridge adapter; an epoch-one checkpoint would receive only nine updates and
  would confound W1 supervision with under-training.
- Seed 42, max length 4096, learning rate 7e-5, effective batch size 16.

## Matched evaluation

- Frozen bridge test: 12 held-out scenarios in IC/OE/SG/CW/EA/SM.
- Four S/T variants per scenario and three rollouts per variant.
- Temperature 1.0, thinking disabled, max eight actions.
- Arms: Base, W1-only SFT, Base + SafeHarness adapted no-LLM.
- Existing Base and Base+Harness trajectories are reused verbatim; only the
  W1-only SFT arm is newly generated.
- All arms use the same Qwen3-32B action Monitor, temperature 0.
- Primary metrics: Monitor risk, Monitor task success, and safe task success.
- Base scenario is the statistical unit; variants and rollouts only measure
  within-scenario variability.

The purpose is not minimum ASR. A weights intervention counts as successful
only when risk falls without replacing task completion with refusal or early
termination. Harness attribution requires an actual guard block plus a paired
trajectory change; Monitor label changes without a block are not attributed to
the harness.

An initial epoch-one generation was stopped before Monitor scoring after the
optimizer-step mismatch was detected. Its 21 partial trajectories are archived
under `previous/epoch1_undertrained_partial/` and are excluded from every
reported result.

## Completion

The matched evaluation and Monitor scoring completed on 2026-11-13. The
machine-readable outputs and detailed Chinese analysis are under
`evaluation/runs/t1_three_rollouts/analysis/`. The primary result is negative
for the W1-only SFT intervention: it raises risk and lowers task success under
the frozen evaluation. This outcome was not used to choose a checkpoint or
modify any episode.
