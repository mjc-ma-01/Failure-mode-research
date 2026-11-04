# AgentSecurityBench results

| Attack | n/arm | No harness ASR / original-task success | Adapted no-LLM ASR / original-task success | Blocks |
|---|---:|---:|---:|---:|
| DPI | 300 | 98.7% / 0.7% | 7.0% / 0.0% | 275 episodes, 348 calls |
| OPI | 300 | 99.7% / 0.7% | 8.0% / 1.0% | 277 episodes, 330 calls |

`original_success` is AgentSecurityBench's expected-achievement string check. It is near zero in both arms under this attack-only protocol and is not a clean benign utility estimate.

The archived runner did not persist the full message/action history. `cases.json` therefore contains the attack tool, block layer, and final answer, but must not be described as a full trajectory.
