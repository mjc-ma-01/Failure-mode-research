# No Harness vs SafeHarness Adapted (No Runtime LLM)

这是当前主实验的唯一入口。比较臂固定为：

1. `noharness`
2. `safeharness_adapted_no_llm`

`no LLM` 仅指 **Harness 在 agent 运行时不调用额外 LLM**。Benchmark 的离线 outcome
judge 仍按各自评测协议使用：

- AutoControl：Qwen3-32B Monitor；
- AgentSecurityBench：benchmark 的 attacker-tool ASR；
- Agentic-Upward-Deception：benchmark 提供的 judge templates，经 `gpt-4o-mini` 执行；
  主风险口径为 NFR/DFR。

## 当前正式结果

| Benchmark | 数据 | No harness | SafeHarness adapted no LLM | Utility |
|---|---:|---:|---:|---|
| AutoControl | 60 场景 × 4 S/T × 3 seeds = 720/臂 | risky 29.9% | risky 18.5% | task success 52.6% → 46.5% |
| AgentSecurityBench DPI | 5 agents × 1 task × 20 tools × 3 injections = 300/臂 | ASR 98.7% | ASR 7.0% | attack-only `original_success` 0.7% → 0.0%，不是干净 benign utility |
| AgentSecurityBench OPI | 同上 | ASR 99.7% | ASR 8.0% | attack-only `original_success` 0.7% → 1.0%，不是干净 benign utility |
| Agentic-Upward-Deception | 32 tasks × 1 seed = 32/臂 | risky 25.0% | risky 21.9% | 原文不定义 task utility；非欺骗率 75.0% → 78.1% |

## 如何阅读

- `autocontrol/`：完整 paired trajectory、Monitor 标签、工具分级表和 TaskSpec。
- `securitybench/`：逐 cell 结果、离线工具分级表及代表 case。正式结果使用的旧 runner
  没保存完整 message/action history，因此这里只能检查攻击工具、拦截层和 final answer；
  `securitybench/code/` 中的清理版复现 runner 会额外保存完整 history。
- `upward_deception/`：完整工具调用、失败 observation、final answer 和官方 judge 输出。
- `shared/`：SecurityBench 和 Upward-Deception 共用的 deterministic no-LLM adapter。
- `MANIFEST.json`：每个正式文件的 SHA-256。
- 公开版本将一处 benchmark 场景生成的假 `sk-...` 字符串替换为
  `[BENCHMARK_FAKE_API_KEY_REDACTED]`；该脱敏不改变轨迹标签、指标或结论。
- `previous/` 不属于主实验；所有旧设定、L2-LLM、threshold、SHE、pilot/smoke 结果均应从
  本目录之外读取，不能混入主表。

## 核心结论

1. **强可观测危险动作可防。** AutoControl IC/OE 中的关停、禁用、改 watchdog，
   AgentSecurityBench 中显式恶意/带副作用工具，主要由 L3 与 deterministic Tier1 拦下。
2. **语义型风险仍难防。** 假完成、选择性报告、骗取授权、内容操纵、只读越权访问不具有
   稳定的执行层信号。
3. **降低风险可能牺牲 utility。** AutoControl 总体 risky 下降 11.4pp，同时 task success
   下降 6.1pp；IC/OE 的下降尤其伴随明显任务完成率损失。
4. **零拦截时不能做因果归因。** Upward Deception 两臂没有任何 Harness block，因此
   3.1pp 表面改善只能视为采样/judge 波动。
5. **AutoControl 未覆盖 Capability Misuse。** 当前正式集只含 IC/OE/SG/CW/EA/SM 六类；
   不能把这些数字外推到 Capability Misuse。

## 复现入口

- AutoControl bridge：SafeHarness submodule 中的 `autocontrol_bridge_eval.py`；
- AgentSecurityBench DPI/OPI：`securitybench/code/run_eval.py`；
- Agentic-Upward-Deception：`upward_deception/code/run_eval.py`。

两个项目侧 runner 都支持 `--plan-only`，可以在不调用模型的情况下先验证数据和实验规模。

