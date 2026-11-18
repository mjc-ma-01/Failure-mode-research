# Harness 实验

本目录保存统一的三臂 Harness 实验：

- `M`：Qwen3.5-9B + benchmark 原有工具循环；
- `M+H`：同一模型接入 ReAct 基础执行框架；
- `M+H+ΔH`：同一个 ReAct 路径叠加 SafeHarness adapted no-LLM。

`H` 是通用 ReAct agent scaffold，`ΔH` 才是安全增量。两者不能合并解释。

AutoControl 使用正式全量六类数据，排除 Capability Misuse：60 个原始场景、四个
`S0T0/S0T1/S1T0/S1T1` 变体、每个变体三个 rollout，每臂 720 条。`M` 从冻结的正式
no-harness 轨迹转换并用与 ReAct 两臂相同的本地 Qwen3-32B Monitor 重新判分；两个 ReAct
臂重新生成。

AgentSecurityBench 和 AutoControl 全量三臂正式结果均已完成。本目录保存了
setting、原始轨迹/判分记录、配对转移、代表案例、分类与总体结果、聚类
bootstrap 区间和 SHA-256 清单。AutoControl 状态为 `complete`。
AgentSecurityBench 已修复批量提前签发 token 的 runner 缺陷，并完成 600 条
clean `M+H+ΔH` 重跑及 1,800 条 DeepSeek 语义判定；正式轨迹中
expired-token event 为 0。旧污染结果只在本地 `previous/` 中存档，
不进入核心结果或协作者 release。

主入口：

- [总结果](RESULTS.md)
- [AutoControl setting](autocontrol/SETTING.md) / [AutoControl 结果](autocontrol/RESULTS.md)
- [AgentSecurityBench setting](securitybench/SETTING.md) / [AgentSecurityBench 结果](securitybench/RESULTS.md)
- [可复现性清单](MANIFEST.json)

## 自包含运行代码

实验专用的运行依赖已经收口到本目录，不再从
`experiments/model_vs_harness_sft/` 导入：

- `shared/react_protocol.py`：冻结的 ReAct 协议；
- `shared/safeharness_no_llm.py`：no-LLM SafeHarness adapter；
- `autocontrol/core_eval.py`、`run_eval_react.py` 与
  `score_monitor_local.py`；
- `autocontrol/tool_tier_registry.json`：285 条工具预注册表；
- `securitybench/canonical_eval.py`、`run_eval_react.py` 与
  `run_eval_react_local.py`；
- `securitybench/asb_tier_table_5agents_principled.json`。

轻量完整性测试：

```bash
python -m unittest experiments/harness实验/tests/test_self_contained.py
```

SecurityBench 本地 runner 按 generation batch 即时构造 Episode 和
SecurityPipeline，避免排队期间 capability token 提前过期。新的复现输出默认写入
`raw/react_arms_token_fixed.jsonl`，不会覆盖历史轨迹。
