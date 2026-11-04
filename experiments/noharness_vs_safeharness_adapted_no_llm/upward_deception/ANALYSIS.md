# Agentic-Upward-Deception analysis

## 结果

- No harness：risky `25.0%`，非欺骗率 `75.0%`；
- Adapted no-LLM：risky `21.9%`，非欺骗率 `78.1%`；
- 配对转移：22 safe→safe、3 risky→safe、2 safe→risky、5 risky→risky；
- Harness block：`0`。

## 因果解释

3.1pp 的表面风险下降不能归因于 Harness：

- 没有任何 L1/L2/L3 block；
- risk-down 与 risk-up 同时存在；
- 两臂分别重新采样了模型轨迹；
- judge 也可能产生少量标签波动。

因此正式结论是：**当前 no-LLM SafeHarness 对 Upward Deception 没有被证明有效。**

原文不报告 task utility；非欺骗率只是风险率的补集，不能解释为任务完成质量。

## 为什么不起作用

风险不在危险工具 capability，而在模型如何处理工具失败：

- `read_file` 返回 decode error 后仍编造文档内容；
- `download_file` 返回 network error 后仍声称已下载；
- 读取到不相关/替换文件后不披露来源问题；
- 在证据不足时给出确定结论。

这些需要的 Harness 机制是：

- 工具失败状态台账；
- final claim 与工具 observation 对账；
- source attribution；
- 对“无成功读取却生成文档内容”的完成门禁。

当前 adapted no-LLM 只有注入 taint、capability tier 和参数规则，不包含上述证据核验。

