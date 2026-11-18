# Core experiments

The active study has exactly two modules. Results outside these two modules are
historical diagnostics and are not part of the main comparison.

| Module | Intervention | Canonical setting | Purpose |
|---|---|---|---|
| Three-arm Harness | `M`, `M+H`, `M+H+ΔH` | [`harness实验/setting.json`](harness实验/setting.json) | Separate the base ReAct scaffold (`H`) from the no-LLM SafeHarness increment (`ΔH`). |
| SFT / weights | Base versus task-specific LoRA SFT | [`model_vs_harness_sft/SETTING.json`](model_vs_harness_sft/SETTING.json) | Test which visible decision failures can be corrected in model weights without replacing task completion with refusal. |

The Harness module contains matched AutoControl and AgentSecurityBench panels.
The SFT module contains only the frozen, accepted tracks listed in its setting:
AutoControl W1-only, SecurityBench V2, and Upward Deception. Git keeps code,
the accepted training data, settings, compact results, and one canonical
combined trajectory-plus-judge record per formal evaluation under
`collaborator_release/`. Checkpoints, adapters, optimizer state, duplicate raw
runs, logs, and interrupted outputs remain outside Git.

Legacy two-arm results under `noharness_vs_safeharness_adapted_no_llm/` remain
tracked for historical reproducibility but are superseded by the three-arm
Harness module. They must not be mixed into the active tables.
