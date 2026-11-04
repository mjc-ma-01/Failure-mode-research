# Agentic-Upward-Deception setting

## 数据

- 从本地 200 条数据中使用当前风险重拆分已经冻结的 32 个任务；
- 任务覆盖五种故障/欺骗构造，具体 UID 见 `tasks.jsonl`；
- 每任务 seed 0；
- 每臂 32 条 episode；
- 模型：`Qwen/Qwen3.5-9B`；
- temperature：0.0（runner 对 agent tool loop 与最终回答均固定为 0.0）；
- 最大 5 个 steps。

## 两个实验臂

### `noharness`

模型直接使用故障、缺失、替换或不相关的 `read_file/download_file` 工具环境。

### `safeharness_adapted_no_llm`

与 SecurityBench 使用同一 no-runtime-LLM pipeline：

- L1 通用注入检测；
- L3 capability ceiling；
- deterministic L2 Tier1；
- 无 Tier2/Tier3 LLM。

该数据的核心工具 `read_file/download_file` 不含注入污点，且没有命中高风险参数，因此本轮
Harness **0 次 block**。

## Outcome judge

- 使用 benchmark 本地提供的 judge templates；
- judge backend：`gpt-4o-mini`；
- 主结果映射：Type 1/2 的 NFR、Type 3 的 DFR、Type 4/5 的 download-failure NFR；
- FFR/HFR 辅助项没有进入本目录主风险率；
- 原文没有 task-success utility；正式报告只给风险率及其补集“非欺骗率”。

原始记录中的 `completed` 是本地 runner 对 `not unsafe` 的旧字段名，不是任务完成效用，主表
不再把它称为 utility。

Harness 在 agent 运行时无 LLM；离线 outcome judge 使用 LLM，两者不能混淆。

