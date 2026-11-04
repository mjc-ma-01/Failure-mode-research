# Failure Mode Research

本项目研究 AI agent 的失败模式，以及模型和执行侧 harness 之间的安全分工：

> 哪些风险具有可观测、可验证的执行信号，适合由 harness 阻断；哪些风险主要依赖语义、
> 诚实性或任务理解，必须由模型能力解决？

当前公开的正式实验比较两个实验臂：

1. **`noharness`**：不接安全执行管线；
2. **`safeharness_adapted_no_llm`**：使用本项目适配的 SafeHarness，但 harness 在 agent
   运行时不调用额外 LLM。

这里的 **no LLM 只限定 harness 本身**。Agent 模型以及 benchmark 规定的离线 outcome
judge 仍可能是 LLM。

## 当前正式实验

正式结果、原始记录、配置快照和完整说明位于：

[`experiments/noharness_vs_safeharness_adapted_no_llm/`](experiments/noharness_vs_safeharness_adapted_no_llm/)

Agent 模型统一为 `Qwen/Qwen3.5-9B`，但每个 benchmark 使用自己的生成温度、任务协议和
outcome judge。

| Benchmark | 本项目使用的数据与规模 | 主要指标 / judge | No harness | SafeHarness adapted no LLM |
|---|---|---|---:|---:|
| [AutoControl Arena](https://github.com/cosmosyi/AutoControl-Arena) | 60 个官方场景，4 个 S/T variants，3 seeds，**720 episodes/臂** | `Qwen/Qwen3-32B` AutoControl Monitor；`is_risky`、task success | risky **29.9%** | risky **18.5%** |
| [AgentSecurityBench](https://github.com/agiresearch/ASB) DPI | 5 agents × 1 task × 20 aggressive tools × 3 injection templates，**300 cells/臂** | attacker-tool ASR | **98.7%** | **7.0%** |
| [AgentSecurityBench](https://github.com/agiresearch/ASB) OPI | 与 DPI 相同，攻击位于工具 observation，**300 cells/臂** | attacker-tool ASR | **99.7%** | **8.0%** |
| [Agentic-Upward-Deception](https://github.com/QingyuLiu/Agentic-Upward-Deception) | 冻结的 32 个任务，覆盖 5 种故障/欺骗构造，**32 episodes/臂** | 官方 judge templates + `gpt-4o-mini`；NFR/DFR | risky **25.0%** | risky **21.9%** |

### 三个 benchmark 分别测什么

#### 1. AutoControl Arena

- 测试压力环境中的 instrumental convergence、oversight evasion、specification gaming、
  covert whistleblowing、evaluation awareness 和 strategic misalignment；
- 本轮覆盖 IC/OE/SG/CW/EA/SM 六类，**没有运行 Capability Misuse**；
- harness 的 block 不直接等于风险标签，最终风险由独立 AutoControl Monitor 判断；
- 风险率下降 `11.4pp`，但 task success 从 `52.6%` 降到 `46.5%`，因此存在安全—效用代价。

详细设置：[SETTING](experiments/noharness_vs_safeharness_adapted_no_llm/autocontrol/SETTING.md) ·
[结果](experiments/noharness_vs_safeharness_adapted_no_llm/autocontrol/RESULTS.md) ·
[分析](experiments/noharness_vs_safeharness_adapted_no_llm/autocontrol/ANALYSIS.md)

#### 2. AgentSecurityBench

这里指的是 `agiresearch/ASB` 的 **AgentSecurityBench**，不是
`thu-coai/Agent-SafetyBench`。

- DPI：攻击指令直接拼入用户输入；
- OPI：攻击指令出现在正常工具返回内容中；
- SafeHarness 运行时只读取离线 capability tier 表，不读取 attacker tool 的
  `kind` 或 attack goal；
- `original_success` 来自强攻击协议下的字符串检查，**不是干净的 benign utility**，
  因而当前结果不能用于声称正常任务效用不受影响。

详细设置：[SETTING](experiments/noharness_vs_safeharness_adapted_no_llm/securitybench/SETTING.md) ·
[结果](experiments/noharness_vs_safeharness_adapted_no_llm/securitybench/RESULTS.md) ·
[分析](experiments/noharness_vs_safeharness_adapted_no_llm/securitybench/ANALYSIS.md)

#### 3. Agentic-Upward-Deception

- 构造文件损坏、文件缺失、decoy、本地/远程工具失败等场景；
- 主要测量 agent 是否如实披露失败，以及是否把无关或替代内容冒充为真实结果；
- 本轮两个实验臂均出现 **0 次 harness block**，因此 `25.0% → 21.9%` 的表面变化只能视为
  模型采样或 judge 波动，不能归因于 harness；
- 原 benchmark 不定义 task-success utility，本项目也不把旧记录中的 `completed` 字段冒充
  为任务效用。

详细设置：[SETTING](experiments/noharness_vs_safeharness_adapted_no_llm/upward_deception/SETTING.md) ·
[结果](experiments/noharness_vs_safeharness_adapted_no_llm/upward_deception/RESULTS.md) ·
[分析](experiments/noharness_vs_safeharness_adapted_no_llm/upward_deception/ANALYSIS.md)

## SafeHarness 适配

本项目使用的不是未修改的上游 SafeHarness，而是公开 fork 的
[`failure-mode-integration`](https://github.com/mjc-ma-01/SafeHarness/tree/failure-mode-integration)
分支，并通过 submodule 固定到 commit `bf2ea55`。

适配内容包括：

- OpenAI-compatible / GLM API 兼容和重试；
- 多工具调用解析与参数保留；
- AutoControl 工具名规范化和模拟工具；
- AutoControl 格式 bridge；
- 供 AgentSecurityBench 和 Upward-Deception 项目侧 runner 使用的共享执行引擎。

因此 fork 中虽然有 `autocontrol_bridge_eval.py`，**它并不是只支持 AutoControl**。
SecurityBench 和 Upward-Deception 的数据切分、runner、tier table 与结果保留在主项目中。

`safeharness_adapted_no_llm` 的运行时安全管线主要由以下部分组成：

- L1：注入 pattern 与不可信来源标记；
- L2：只使用 deterministic Tier 1 打分，`score >= 0.7` 阻断；
- L3：离线工具 capability tier 和最高 `network` 的执行 ceiling；
- 不使用 L2 Tier 2 judge LLM 或 Tier 3 causal LLM。

## 其他 benchmark 的使用边界

本地开发环境曾检出 11 个公开 benchmark，但 `data/` 体积较大且可重新获取，因此没有上传。
只有前三个进入当前正式两臂主表；其余项目属于历史实验、方法开发或 taxonomy 覆盖参考。

| Benchmark | 当前用途 | 是否进入当前正式主表 |
|---|---|---|
| AutoControl Arena | 正式两臂实验 | **是** |
| AgentSecurityBench | 正式 DPI/OPI 两臂实验 | **是** |
| Agentic-Upward-Deception | 正式两臂实验 | **是** |
| [Agent-SafetyBench](https://github.com/thu-coai/Agent-SafetyBench) | 早期 SafeHarness/SHE 分析、失败 taxonomy；也是 SafeHarbor 论文的官方评测集之一 | 否 |
| [AgentDojo](https://github.com/ethz-spylab/agentdojo) | 历史 SHE/harness-evolution 实验与注入防御研究 | 否 |
| [AgentHarm](https://huggingface.co/datasets/ai-safety-institute/AgentHarm) | 历史 SHE 实验、语义 judge 验证；也是 SafeHarbor 论文的官方评测集之一 | 否 |
| [AgentDyn](https://github.com/leolee99/AgentDyn) | taxonomy / 防御覆盖参考 | 否 |
| [agentic-misalignment](https://github.com/anthropic-experimental/agentic-misalignment) | taxonomy 与案例参考 | 否 |
| [ImpossibleBench](https://github.com/safety-research/impossiblebench) | 不可能任务与诚实失败参考 | 否 |
| [MACHIAVELLI](https://github.com/aypan17/machiavelli) | 长程决策风险 taxonomy 参考 | 否 |
| [Propensity Evaluation](https://github.com/scaleapi/propensity-evaluation) | agent propensity / 风险覆盖参考 | 否 |

历史结果不得与当前
`noharness` vs `safeharness_adapted_no_llm` 主表直接合并。

## 外部 harness 与 submodule

| 路径 | 来源 | 用途 |
|---|---|---|
| `external_harnesses/SafeHarness` | 本项目公开 fork | 当前三个正式 benchmark 共用的适配执行引擎 |
| `external_harnesses/SafeHarbor` | 官方 SafeHarbor | 方法研究；当前发布 artifact 与 loader 存在兼容问题，尚未声称本项目 benchmark 成绩 |
| `external_harnesses/SHE_official` | 官方 SHE | 历史/对比研究 |
| `evolve/harness/upstream/EvoSafeHarness` | 官方 EvoSafeHarness | harness evolution 方法起点 |

SafeHarbor（arXiv:2605.05704）的机制、官方数据和兼容性审计见
[`docs/SAFEHARBOR_2605.05704.md`](docs/SAFEHARBOR_2605.05704.md)。

## 克隆与查看结果

必须同时初始化 submodule：

```bash
git clone --recurse-submodules \
  https://github.com/mjc-ma-01/Failure-mode-research.git
cd Failure-mode-research
```

如果已经普通克隆：

```bash
git submodule update --init --recursive
```

正式结果和原始记录已经包含在仓库中，查看结果不需要下载 `data/`。

## 获取正式 benchmark 源码

如需重新运行或检查上游数据：

```bash
mkdir -p data
git clone https://github.com/cosmosyi/AutoControl-Arena.git \
  data/AutoControl-Arena
git clone https://github.com/agiresearch/ASB.git \
  data/AgentSecurityBench
git clone https://github.com/QingyuLiu/Agentic-Upward-Deception.git \
  data/Agentic-Upward-Deception
git -C data/AgentSecurityBench checkout 1f561dccf92d55302368fa67679b4ba9d9c8fdc4
git -C data/Agentic-Upward-Deception checkout b26151c7195111271feba64fb15db6227f25f51b
```

`data/` 被 `.gitignore` 排除，不会意外上传。正式发布使用的 AgentSecurityBench checkout
为 commit `1f561dc`，Agentic-Upward-Deception 为 `b26151c`；AutoControl 的正式 TaskSpec
输入已快照到 canonical experiment 的 `autocontrol/config/` 并由 Manifest 校验。

## 复现入口

先在不调用模型的情况下检查任务规模：

```bash
python experiments/noharness_vs_safeharness_adapted_no_llm/securitybench/code/run_eval.py \
  --out /tmp/securitybench-reproduction.jsonl \
  --plan-only

python experiments/noharness_vs_safeharness_adapted_no_llm/upward_deception/code/run_eval.py \
  --out-dir /tmp/upward-deception-reproduction \
  --plan-only
```

预期输出：

```text
planned cells: 1200
planned episodes: 64
```

完整运行需要通过本地环境变量提供 OpenAI-compatible endpoint，仓库不保存凭据：

```bash
export OPENAI_BASE_URL=https://your-endpoint.example/v1
export OPENAI_API_KEY=your-local-secret
```

具体复现说明：

- AutoControl：
  [`SafeHarness/FAILURE_MODE_INTEGRATION.md`](https://github.com/mjc-ma-01/SafeHarness/blob/failure-mode-integration/FAILURE_MODE_INTEGRATION.md)
- AgentSecurityBench：
  [`securitybench/code/README.md`](experiments/noharness_vs_safeharness_adapted_no_llm/securitybench/code/README.md)
- Agentic-Upward-Deception：
  [`upward_deception/code/README.md`](experiments/noharness_vs_safeharness_adapted_no_llm/upward_deception/code/README.md)

## 仓库结构

| 路径 | 内容 |
|---|---|
| `experiments/noharness_vs_safeharness_adapted_no_llm/` | 当前唯一正式实验入口 |
| `evolve/harness/` | harness evolution 代码、配置和研究记录 |
| `evolve/policy/` | model-side SFT/RL 方向，占位与规划 |
| `external_harnesses/` | 外部 harness submodules |
| `docs/` | 方法、judge、失败标签和论文审计 |
| `figures/` | 论文与方法图 |
| `archive/` | 早期探索材料，不属于当前主表 |
| `data/` | 本地 benchmark checkout；被忽略，不上传 |

## 结果完整性与公开发布说明

- canonical experiment 的 `MANIFEST.json` 记录每个正式文件的 SHA-256；
- 一处 benchmark 场景生成的假 `sk-...` 字符串已替换为
  `[BENCHMARK_FAKE_API_KEY_REDACTED]`，不影响标签、指标或结论；
- API keys、`.env`、venv、缓存和大型上游数据均不进入仓库；
- `experiments/previous/` 是本地历史归档，不属于当前正式实验，也不上传。

## 当前状态

- 当前三 benchmark 的 `noharness` vs `safeharness_adapted_no_llm` 正式实验已整理并公开；
- SecurityBench 和 Upward-Deception 的清理版复现 runner 已包含；
- SafeHarness 适配 fork 与四个外部 submodule 已公开并固定版本；
- 更广泛的 harness evolution 和 model-side SFT/RL 仍在进行中。
