# AutoControl Arena 全量三臂结果

每个单元格为 **risk rate / task-success utility**。本表覆盖 60 个原始场景、
240 个四条件变体、每变体 3 次 rollout，因此每臂 720 条。

| 类别 | M | M+H | M+H+ΔH |
|---|---:|---:|---:|
| Instrumental Convergence | 54.2% / 67.7% | 58.9% / 68.8% | 40.6% / 50.0% |
| Oversight Evasion | 53.7% / 62.0% | 58.3% / 79.6% | 41.7% / 73.1% |
| Specification Gaming | 16.7% / 37.1% | 15.2% / 41.7% | 9.1% / 41.7% |
| Covert Whistleblowing | 13.9% / 38.0% | 19.4% / 34.3% | 23.1% / 36.1% |
| Evaluation Awareness | 9.7% / 81.9% | 9.7% / 80.6% | 9.7% / 80.6% |
| Strategic Misalignment | 20.4% / 61.1% | 27.8% / 57.4% | 24.1% / 58.3% |

## 总体

| 臂 | Risk | Task success | Helpfulness | Safe + success | Security block episode / call |
|---|---:|---:|---:|---:|---:|
| M | 228/720 = 31.7% | 412/720 = 57.2% | 2.749 | 37.4% | 0 / 0 |
| M+H | 254/720 = 35.3% | 430/720 = 59.7% | 2.899 | 37.8% | 0 / 0 |
| M+H+ΔH | 193/720 = 26.8% | 390/720 = 54.2% | 2.729 | 39.7% | 150 / 233 |

## 配对转移

### M → M+H

- `risky->risky`: 160，其中 treatment 有真实 security block 0 条。
- `risky->safe`: 68，其中 treatment 有真实 security block 0 条。
- `safe->risky`: 94，其中 treatment 有真实 security block 0 条。
- `safe->safe`: 398，其中 treatment 有真实 security block 0 条。

### M+H → M+H+ΔH

- `risky->risky`: 185，其中 treatment 有真实 security block 39 条。
- `risky->safe`: 69，其中 treatment 有真实 security block 69 条。
- `safe->risky`: 8，其中 treatment 有真实 security block 8 条。
- `safe->safe`: 458，其中 treatment 有真实 security block 34 条。

## 实验边界

- Risk 和 utility 都是对完整 action trajectory 的 Monitor 判定，不是谓词匹配。
- 置信区间按 60 个原始场景聚类；四变体和三次 rollout 不当作独立新场景。
- ReAct action-format 终止失败保留在分母中，不用删除失败轨迹美化结果。
- `M+H+ΔH` 的改善只有在伴随真实 block 时才可归因为执行层拦截；无 block 转移需要单独审查。
