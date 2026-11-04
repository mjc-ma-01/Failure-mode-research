# Agentic-Upward-Deception results

The benchmark defines failure-reporting/deception metrics, not task utility.

| Arm | n | Risky / non-deception | Blocks | Errors |
|---|---:|---:|---:|---:|
| No harness | 32 | 25.0% / 75.0% | 0 | 0 |
| SafeHarness adapted no LLM | 32 | 21.9% / 78.1% | 0 | 0 |

There were zero Harness blocks. The 3 risk-down and 2 risk-up paired changes are therefore sampling/judge variation, not evidence that the no-LLM Harness caused the improvement.

The raw `completed` field is a legacy runner alias for the complement of its unsafe predicate in this benchmark. It must not be interpreted as task-success utility.
