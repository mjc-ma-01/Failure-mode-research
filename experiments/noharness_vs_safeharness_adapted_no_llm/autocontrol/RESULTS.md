# AutoControl results

Outcome labels are from the offline AutoControl-rubric Monitor, not from SafeHarness.

| Category | n/arm | No harness risky / task success | Adapted no-LLM risky / task success | Blocks |
|---|---:|---:|---:|---:|
| CW | 108 | 6.5% / 31.5% | 6.5% / 35.2% | 3 episodes, 6 calls |
| EA | 72 | 1.4% / 76.4% | 0.0% / 73.6% | 3 episodes, 3 calls |
| IC | 192 | 52.1% / 64.1% | 24.5% / 42.7% | 63 episodes, 121 calls |
| OE | 108 | 49.1% / 63.9% | 25.9% / 48.1% | 20 episodes, 28 calls |
| SG | 132 | 27.3% / 35.6% | 27.3% / 42.4% | 2 episodes, 2 calls |
| SM | 108 | 16.7% / 47.2% | 13.9% / 50.0% | 5 episodes, 5 calls |
| **Overall** | **720** | **29.9% / 52.6%** | **18.5% / 46.5%** | **96 episodes, 165 calls** |

Helpfulness means: `2.67 -> 2.54`.

Important: paired label changes without a recorded block are sampling/judge variation, not causal defense wins. See `ANALYSIS.md` and `cases.json`.

Generation audit: all 1,440 trajectories received valid Monitor labels. Intermediate proposal-JSON parse/retry events occurred in 27 no-harness and 23 adapted episodes; max-step termination occurred in 94 and 100 episodes.
