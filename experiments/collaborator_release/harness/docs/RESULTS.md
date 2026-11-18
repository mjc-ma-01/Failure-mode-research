# Harness 实验：M / M+H / M+H+ΔH

## AutoControl Arena（全量六类）

60 个原始场景、240 个四条件变体、每变体 3 次 rollout，每臂 720 条；
Capability Misuse 已排除。

| 臂 | Risk rate | Task-success utility | Safe + success | 真实 security block episode / call |
|---|---:|---:|---:|---:|
| `M` | **31.7%** | **57.2%** | 37.4% | 0 / 0 |
| `M+H` | **35.3%** | **59.7%** | 37.8% | 0 / 0 |
| `M+H+ΔH` | **26.8%** | **54.2%** | 39.7% | 150 / 233 |

ReAct 单独使 risk 上升 3.6 个百分点，utility 上升 2.5 个百分点；它不是稳定的安全层。
在相同 ReAct 基座上，ΔH 使 risk 下降 8.5 个百分点，但 utility 下降 5.6 个百分点；
69 条 risky→safe 全部伴随真实 block，同时 8 条 safe→risky 也都伴随 block。

详细分类数字见 [AutoControl 结果](autocontrol/RESULTS.md)。

## AgentSecurityBench（DPI / OPI）

每臂 600 条；DPI 300、OPI 300，temperature 0。

| 臂 | Semantic ASR | Strict utility | 真实 block episode / call |
|---|---:|---:|---:|
| `M` | **97.2%** | 0.0% | 0 / 0 |
| `M+H` | **92.2%** | 0.0% | 0 / 0 |
| `M+H+ΔH` | **7.0%** | 0.2% | 513 / 661 |

正式 outcome 已改为单一 `deepseek-v4-pro-0813` 对完整轨迹做语义判定；旧字符串
marker 只作分歧诊断。这里的 strict utility 要求原任务完成、声明有证据、执行一致且
没有过度拒绝。token-fixed 重跑中 600 条 `M+H+ΔH` trajectory 的 expired-token
block 为 0：535 次 L3 ceiling、126 次 L2 Tier1，共 513 个实际 block episode。
clean 结果显示 `ΔH` 强于阻止攻击，但 strict utility 仅 0.2%，过度拒绝为 46.8%。
详细数字见 [AgentSecurityBench 结果](securitybench/RESULTS.md)。

## 此目录的用法

这是待后续机制分析的冻结三臂数据。后续归因时必须区分：

- `M → M+H`：执行 scaffold 效应，没有安全 block；
- `M+H → M+H+ΔH`：安全增量，只有伴随真实 block 的转移才可归因为 harness 拦截；
- 完全相同的 Monitor prompt 复用同一 verdict，避免 judge 噪声被误认为安全层因果。
