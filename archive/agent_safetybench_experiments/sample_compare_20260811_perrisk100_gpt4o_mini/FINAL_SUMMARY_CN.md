# Agent-SafetyBench gpt-4o-mini per-risk-100 final results

- Agent model: `gpt-4o-mini`
- Judge model: `gpt-4.1`
- Intended design: 8 risk categories x 100 tasks x 4 conditions = 3200 trajectories
- Final analysis set: 3199 valid trajectories; excluded `id=35/she` due repeated NewAPI connection reset on raw PHP webshell payload
- Conditions: `base`, `unprotected`, `safeharness`, `she`

## Overall

| condition | n | unsafe_rate | unsafe_count | safe_rate | completion_rate | completed | block_rate | blocked_rows | avg_tool_calls | avg_blocked | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| base | 800 | 5.5% | 44 | 94.5% | 21.2% | 170 | 0.0% | 0 | 0.0 | 0.0 | 0 |
| unprotected | 800 | 29.5% | 236 | 70.5% | 42.2% | 338 | 0.0% | 0 | 1.065 | 0.0 | 0 |
| safeharness | 800 | 23.4% | 187 | 76.6% | 42.4% | 339 | 0.4% | 3 | 1.074 | 0.006 | 0 |
| she | 799 | 19.9% | 159 | 80.1% | 33.7% | 269 | 13.5% | 108 | 0.895 | 0.148 | 0 |

## By Risk And Condition

| risk | condition | n | unsafe_rate | unsafe_count | completion_rate | completed | block_rate | avg_tool_calls | avg_blocked |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Leak sensitive data / information | base | 100 | 1.0% | 1 | 4.0% | 4 | 0.0% | 0.0 | 0.0 |
| Leak sensitive data / information | unprotected | 100 | 28.0% | 28 | 41.0% | 41 | 0.0% | 1.51 | 0.0 |
| Leak sensitive data / information | safeharness | 100 | 24.0% | 24 | 42.0% | 42 | 2.0% | 1.52 | 0.02 |
| Leak sensitive data / information | she | 100 | 18.0% | 18 | 22.0% | 22 | 21.0% | 1.06 | 0.22 |
| Lead to property loss | base | 100 | 1.0% | 1 | 7.0% | 7 | 0.0% | 0.0 | 0.0 |
| Lead to property loss | unprotected | 100 | 34.0% | 34 | 51.0% | 51 | 0.0% | 1.15 | 0.0 |
| Lead to property loss | safeharness | 100 | 28.0% | 28 | 50.0% | 50 | 0.0% | 1.15 | 0.0 |
| Lead to property loss | she | 100 | 25.0% | 25 | 41.0% | 41 | 12.0% | 1.04 | 0.14 |
| Spread unsafe information / misinformation | base | 100 | 2.0% | 2 | 42.0% | 42 | 0.0% | 0.0 | 0.0 |
| Spread unsafe information / misinformation | unprotected | 100 | 41.0% | 41 | 54.0% | 54 | 0.0% | 0.98 | 0.0 |
| Spread unsafe information / misinformation | safeharness | 100 | 40.0% | 40 | 56.0% | 56 | 0.0% | 1.0 | 0.0 |
| Spread unsafe information / misinformation | she | 100 | 34.0% | 34 | 53.0% | 53 | 9.0% | 0.93 | 0.11 |
| Lead to physical harm | base | 100 | 2.0% | 2 | 20.0% | 20 | 0.0% | 0.0 | 0.0 |
| Lead to physical harm | unprotected | 100 | 46.0% | 46 | 66.0% | 66 | 0.0% | 1.77 | 0.0 |
| Lead to physical harm | safeharness | 100 | 30.0% | 30 | 63.0% | 63 | 1.0% | 1.77 | 0.03 |
| Lead to physical harm | she | 100 | 19.0% | 19 | 39.0% | 39 | 27.0% | 1.43 | 0.3 |
| Violate law or ethics / damage society | base | 100 | 6.0% | 6 | 26.0% | 26 | 0.0% | 0.0 | 0.0 |
| Violate law or ethics / damage society | unprotected | 100 | 30.0% | 30 | 41.0% | 41 | 0.0% | 0.94 | 0.0 |
| Violate law or ethics / damage society | safeharness | 100 | 23.0% | 23 | 40.0% | 40 | 0.0% | 0.93 | 0.0 |
| Violate law or ethics / damage society | she | 100 | 19.0% | 19 | 34.0% | 34 | 18.0% | 0.78 | 0.18 |
| Compromise availability | base | 100 | 1.0% | 1 | 25.0% | 25 | 0.0% | 0.0 | 0.0 |
| Compromise availability | unprotected | 100 | 27.0% | 27 | 54.0% | 54 | 0.0% | 1.64 | 0.0 |
| Compromise availability | safeharness | 100 | 14.0% | 14 | 56.0% | 56 | 0.0% | 1.67 | 0.0 |
| Compromise availability | she | 100 | 21.0% | 21 | 52.0% | 52 | 9.0% | 1.49 | 0.11 |
| Contribute to harmful / vulnerable code | base | 100 | 25.0% | 25 | 46.0% | 46 | 0.0% | 0.0 | 0.0 |
| Contribute to harmful / vulnerable code | unprotected | 100 | 26.0% | 26 | 31.0% | 31 | 0.0% | 0.53 | 0.0 |
| Contribute to harmful / vulnerable code | safeharness | 100 | 22.0% | 22 | 32.0% | 32 | 0.0% | 0.55 | 0.0 |
| Contribute to harmful / vulnerable code | she | 99 | 16.2% | 16 | 28.3% | 28 | 12.1% | 0.424 | 0.121 |
| Produce unsafe information / misinformation | base | 100 | 6.0% | 6 | 0.0% | 0 | 0.0% | 0.0 | 0.0 |
| Produce unsafe information / misinformation | unprotected | 100 | 4.0% | 4 | 0.0% | 0 | 0.0% | 0.0 | 0.0 |
| Produce unsafe information / misinformation | safeharness | 100 | 6.0% | 6 | 0.0% | 0 | 0.0% | 0.0 | 0.0 |
| Produce unsafe information / misinformation | she | 100 | 7.0% | 7 | 0.0% | 0 | 0.0% | 0.0 | 0.0 |

## Deltas Versus Unprotected

| condition | unsafe_rate_delta_pp | completion_delta_pp |
|---|---:|---:|
| base | -24.0 | -21.0 |
| safeharness | -6.1 | 0.1 |
| she | -9.6 | -8.6 |
