# Agent-SafetyBench by failure mode: gpt-4o-mini defenses

Analysis set: `records_clean_excluding_id35_she.jsonl` (3199 valid trajectories). `base` omitted. Multi-label expansion: samples with multiple failure modes are counted once in each listed mode.

## Failure Mode Definitions

1. Generate harmful content directly without tool calls
2. Call tools with incomplete necessary information
3. Call tools before obtaining complete information
4. Ignore known constraints when calling tools
5. Ignore implicit/potential risks before acting
6. Use incorrect tool parameters
7. Call tools with known safety/legal issues
8. Fail to call necessary tools
9. Over-trust tool results without validation
10. Fail to filter/prioritize tool results

## Unsafe Rate By Failure Mode

| mode | n_unprot | unprotected unsafe | SafeHarness unsafe | ΔSH pp | SHE unsafe | ΔSHE pp | SH block | SHE block |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 139 | 8.6% (12) | 8.6% (12) | +0.0 | 9.4% (13) | +0.8 | 0.0% | 0.7% |
| 2 | 96 | 21.9% (21) | 12.5% (12) | -9.4 | 13.5% (13) | -8.3 | 0.0% | 5.2% |
| 3 | 34 | 38.2% (13) | 14.7% (5) | -23.5 | 20.6% (7) | -17.6 | 0.0% | 20.6% |
| 4 | 148 | 34.5% (51) | 23.0% (34) | -11.5 | 15.5% (23) | -18.9 | 0.0% | 29.7% |
| 5 | 172 | 34.3% (59) | 29.1% (50) | -5.2 | 18.6% (32) | -15.7 | 1.2% | 23.3% |
| 6 | 53 | 18.9% (10) | 9.4% (5) | -9.4 | 3.8% (2) | -15.1 | 0.0% | 9.4% |
| 7 | 74 | 36.5% (27) | 27.0% (20) | -9.5 | 29.7% (22) | -6.8 | 0.0% | 6.8% |
| 8 | 38 | 28.9% (11) | 15.8% (6) | -13.2 | 21.1% (8) | -7.9 | 0.0% | 18.4% |
| 9 | 118 | 53.4% (63) | 50.8% (60) | -2.5 | 39.3% (46) | -14.1 | 0.8% | 14.5% |
| 10 | 61 | 26.2% (16) | 19.7% (12) | -6.6 | 21.3% (13) | -4.9 | 1.6% | 11.5% |

## Completion Rate By Failure Mode

| mode | unprotected completion | SafeHarness completion | ΔSH pp | SHE completion | ΔSHE pp |
|---:|---:|---:|---:|---:|---:|
| 1 | 6.5% (9) | 7.2% (10) | +0.7 | 5.8% (8) | -0.7 |
| 2 | 39.6% (38) | 39.6% (38) | +0.0 | 37.5% (36) | -2.1 |
| 3 | 64.7% (22) | 64.7% (22) | +0.0 | 50.0% (17) | -14.7 |
| 4 | 53.4% (79) | 54.1% (80) | +0.7 | 26.4% (39) | -27.0 |
| 5 | 39.0% (67) | 39.0% (67) | +0.0 | 25.0% (43) | -14.0 |
| 6 | 54.7% (29) | 52.8% (28) | -1.9 | 47.2% (25) | -7.5 |
| 7 | 35.1% (26) | 36.5% (27) | +1.4 | 43.2% (32) | +8.1 |
| 8 | 63.2% (24) | 60.5% (23) | -2.6 | 50.0% (19) | -13.2 |
| 9 | 63.6% (75) | 64.4% (76) | +0.8 | 51.3% (60) | -12.3 |
| 10 | 72.1% (44) | 68.9% (42) | -3.3 | 63.9% (39) | -8.2 |

## Pairwise Safety Transitions Vs Unprotected

| mode | defense | comparable_n | unsafe->safe | unsafe->unsafe | safe->unsafe | safe->safe |
|---:|---|---:|---:|---:|---:|---:|
| 1 | safeharness | 139 | 4 | 8 | 4 | 123 |
| 1 | she | 138 | 3 | 8 | 5 | 122 |
| 2 | safeharness | 96 | 9 | 12 | 0 | 75 |
| 2 | she | 96 | 13 | 8 | 5 | 70 |
| 3 | safeharness | 34 | 8 | 5 | 0 | 21 |
| 3 | she | 34 | 8 | 5 | 2 | 19 |
| 4 | safeharness | 148 | 24 | 27 | 7 | 90 |
| 4 | she | 148 | 33 | 18 | 5 | 92 |
| 5 | safeharness | 172 | 13 | 46 | 4 | 109 |
| 5 | she | 172 | 36 | 23 | 9 | 104 |
| 6 | safeharness | 53 | 6 | 4 | 1 | 42 |
| 6 | she | 53 | 8 | 2 | 0 | 43 |
| 7 | safeharness | 74 | 10 | 17 | 3 | 44 |
| 7 | she | 74 | 12 | 15 | 7 | 40 |
| 8 | safeharness | 38 | 5 | 6 | 0 | 27 |
| 8 | she | 38 | 6 | 5 | 3 | 24 |
| 9 | safeharness | 118 | 7 | 56 | 4 | 51 |
| 9 | she | 117 | 19 | 43 | 3 | 52 |
| 10 | safeharness | 61 | 5 | 11 | 1 | 44 |
| 10 | she | 61 | 7 | 9 | 4 | 41 |

## Notes

- Negative delta means the defense reduced unsafe rate versus unprotected. Positive delta means worse than unprotected.
- SafeHarness is most plausibly ineffective where ΔSH is near zero or positive, especially if block rate is also near zero.
