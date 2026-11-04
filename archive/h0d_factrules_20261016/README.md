# H0-D 事实型规则（归档 2026-10-16）

来源：`evolve/harness/configs/harness/H0D/`（system_prompt.md / rule_bank.jsonl / tool_policy.json）

性质：**事实型（fact-based）规则**——只看运行时事实（roles / known_counterparties / untrusted_seen /
require_confirm），不做文本/模式匹配。实测效果：脚本"必做型攻击者" ASR 88.9%（纯 H0）→ 2.8%（H0-D）。

被替换原因：按用户要求切换到 **SHE 的 setting**（内容/模式型规则 + safety_memory + tool_policy detector）。
本目录保留用于对照与回归（若 SHE 版表现更差，可回退并做 A/B）。
