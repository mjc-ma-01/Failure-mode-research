# Status

Status: **complete** (2026-11-13)

- W1-only dataset built and audited: 140 rows, 35 independent scenarios, six categories, no W2, no Capability Misuse.
- Qwen3.5-9B LoRA trained for the fixed three-epoch / 27-step recipe.
- Matched T=1.0, three-rollout evaluation completed: Base, W1-only SFT, and Base+SafeHarness, 144 episodes per arm.
- Qwen3-32B Monitor completed with zero parse failures.
- Three-arm assembly passed: 432 records, 144 paired cells, exact seed/task coverage, zero Capability Misuse rows.
- Formal result and case analysis are under `evaluation/runs/t1_three_rollouts/analysis/`.

Primary finding: W1-only SFT is a negative result (risk 30.6% -> 47.2%, utility 61.8% -> 48.6%). SafeHarness lowers risk to 16.0% but utility to 37.5%. See `INSIGHTS_CN.md` for paired causal attribution and lever-selection rules.
