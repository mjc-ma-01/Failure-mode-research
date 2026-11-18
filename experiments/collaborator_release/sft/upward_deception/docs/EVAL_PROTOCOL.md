# Frozen Paired Evaluation Protocol

## Objective

Test whether model-side SFT reduces failure concealment and result fabrication,
without replacing useful behavior with blanket refusal.

## Frozen model arms

- `base`: cached `Qwen/Qwen3.5-9B` revision
  `c202236235762e1c871ad0ccb60c8ee5ba337b9a`;
- `sft`: the same base plus the epoch-3 LoRA adapter from
  `training/runs/qwen35_9b_lora_v5/final_adapter`.

The final epoch was fixed before evaluation. Test outcomes are not used to select a
checkpoint.

## Frozen task panel

The 40-task `output/split/test.jsonl` panel is used. It contains the 32 canonical
tasks from the no-harness versus SafeHarness experiment plus eight tasks added
before training to balance task-type coverage. No train task appears in test.

Each task is evaluated under three matched environments:

1. `failure`: official benchmark-style failed, insufficient, or substituted source;
2. `success`: a held-out, independently validated source is available;
3. `authorized_fallback`: the primary source fails, but a trusted instruction
   explicitly authorizes `verified_cache.txt` after the primary attempt.

The source fixtures are generated only for held-out evaluation and pass local,
source-sufficiency, and adversarial validation. They are never added to SFT data.
The failure condition does not reveal authoritative fixture content.
For Type 2, `failure` uses the benchmark's original irrelevant `file_content`,
not a generated insufficient-source fixture.

## Agent setting

- temperature: `0`;
- one deterministic rollout per task, arm, and condition;
- identical Qwen chat template and tools for both arms;
- maximum six tool rounds, followed by an explicit final-answer request;
- complete tool events and final response are retained;
- no harness and no runtime judge.

## Outcomes

### Primary safety outcome

Official Agentic-Upward-Deception templates judged by `gpt-4o-mini`:

- Type 1/2: NFR;
- Type 3: DFR;
- Type 4/5: download-failure NFR.

`risky=true` uses only these official benchmark definitions.

### Utility and mechanism outcomes

`deepseek-v4-pro`, temperature zero, separately judges:

- evidence grounding, failure disclosure, source attribution, and authorization;
- feasible task utility and over-refusal.

The main utility endpoint is utility pass rate in `success`. The fallback endpoint
is the evidence-and-utility composite pass rate in `authorized_fallback`.
The failure-condition utility score means truthful feasible handling, not ordinary
task completion.

## Analysis

- paired Base-to-SFT transition counts;
- absolute percentage-point changes;
- exact paired McNemar/binomial test for discordant failure-risk labels;
- Wilson 95% confidence intervals;
- breakdown by the five official task types;
- full trace review of risk-down, risk-up, retained-risk, utility-loss, and
  successful-fallback cases.

No keyword detector determines the formal outcomes.
