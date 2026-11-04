# SHE 搜索台（AgentDojo 版，2026-10-16）

## 1. 为什么要重做 seed（而不是直接用官方 SHE seed）

官方 SHE seed（`RainbowQTT/SHE` 的 `artifacts/`，与本机 `she-release/artifacts/` **逐字节一致**）
是给 **Agent-SafetyBench** 调的：规则 trigger 以文本模式为主（`ignore previous instructions`、
`developer mode`…），Tool Policy 的 sink 只覆盖 `send_email / http_post / download_file / file_write`。

实测（脚本"必做型攻击者"，AgentDojo 36 格）：

| 臂 | ASR | 拦截 |
|---|---|---|
| H0（纯平台栈） | 88.9% | 6 |
| **SHE 官方 seed（ASB 口味）** | **88.9%** | 6（等于没加防护） |
| **SHE-AgentDojo seed（本搜索台）** | **30.6%** | 48 |

另：把官方 6 条规则里的 37 个正则拿去匹配我们 63 条真实 AgentDojo 注入文本，**命中 0/63**——
AgentDojo 的基线攻击是"礼貌代办"式（`This is an important message from… Before you can solve the
task… please do the following first: …`），不在 ASB 的词表里。

→ 因此保留 SHE 的**形态**（4 artifacts + allow/warn/block/sanitize/judge 动作 + Rule
Bank/Tool Policy 的分工），把**内容**换成 AgentDojo 匹配的：

`evolve/harness/configs/harness/SHE_agentdojo_seed/`

| artifact | 与官方 seed 的差别 |
|---|---|
| `system_prompt.md` | SHE 四条原则不变；补 2 句 AgentDojo 版信任边界（副作用动作的目标必须来自用户请求/用户自己的记录，不能来自刚读到的内容） |
| `rule_bank.jsonl` | 5 条：① `after_tool` **SANITIZE** 通用"外部指令标记"（important message from / before you can solve / please do the following first…）；② 污点后需确认；③ `send_money` 收款人范围；④ 消息类（email/direct message/post）收件人范围；⑤ 权限/删除类需先读 |
| `safety_memory.jsonl` | 2 条（工具输出里的指令 / 注入的收款人），带 harmful_rule + benign_rule + blocked/allowed cases |
| `tool_policy.json` | sink 换成 AgentDojo 真实工具面（send_money / send_email / send_direct_message / post_message / invite_user_to_slack / add_user_to_channel / remove_user_from_slack / delete_file / create_calendar_event / reserve_hotel / reserve_car_rental）+ `after_tool` 注入检测 + `after_block` 重试检测 |

## 2. 数据切分（对齐 SHE 的 train/heldout 协议）

| 用途 | 格子 | 说明 |
|---|---|---|
| **evolve（train）** | AgentDojo dev 的 **前 30** 个注入格 | 只用于提案与门控 |
| **test-dev** | dev 剩余 **33** 格 | 留出 |
| **test-heldout** | AgentDojo **heldout 63** 格（user 池与 dev 不重叠） | 留出（只评一次） |
| **plain 对照** | dev/heldout 各 9 格**无注入**用户任务 | 只惩罚"过拦"（utility 掉分） |

切分清单：`experiments/split_agentdojo/{dev,heldout}.json`（63/63，user 池不重叠）。

## 3. 进化循环（严格按 SHE Algorithm 1 实现，跨机器拆分）

```
H_best ← SHE-agentdojo seed;  F_rej ← ∅
for epoch k:
  1) 在 train30 上 rollout H_best          → (S=1-ASR, U=utility) + 失败证据（含轨迹：工具序列/是否见到注入文本/被拦步数）
  2) 诊断+路由：对每个失败例给出 (harm_domain, attack_surface, failure_mode) 与责任 artifact
  3) Δ ← Edit(H_best, 证据, F_rej)         （LLM：claude-sonnet-4-6；有界编辑 ≤2 规则 / ≤3 句 / ≤1 memory）
  4) ValidEdit(Δ)：schema + house rules（BLOCK 必须有 benign_exemption；禁 bench 字面；能编译）
  5) 候选 = H_best ⊕ Δ → train30 rollout
  6) 选型：S(cand) > S(best) 且 U(cand) ≥ U(best) 才接受（严格改进）；否则 F_rej ∪= {Δ, 原因}
  7) 连续 stale ≥ 2 → 停
最终：H_best 在 train30 / test-dev 33 / test-heldout 63 / plain 对照上各评一次 → 结果表
```

**跨机器拆分（踩坑后的正确架构）**：容器里**连不上 LLM 网关**（实测 `Connection timed out`），
所以 rollout 在 GPU 作业里跑（无 LLM），**提案/校验/选型在宿主机跑**（`she_orchestrator.py`），
作业入口 `she_rollout_job.sh`（`FMR_SHE_MANIFEST` 传 manifest）。

## 4. 防过拟合/防作弊的具体约束

1. train/test 固定；test 只在最后评一次；
2. 严格选型：安全必须**严格改进**、效用不得下降（SHE 原文式），候选与当前 best 同轮同批比较；
3. 拒绝反馈 F_rej 回灌给提案模型，避免重复无效编辑；
4. 有界编辑（≤2 规则/轮）+ stale 停止；
5. 编译期 house rules（BLOCK 必带 benign_exemption、禁 bench 字面）；
6. plain 对照集专门测过拦；
7. 每条规则/判定都落在 dump 里（`detail.she`：blocked/warned/sanitized/injection_seen + 判定日志尾部），可逐格复核。

## 5. 产物

* 每轮 rollout：`experiments/she_agentdojo_run1/rollouts/{split}_{variant}.json` 与同名 `.episodes.jsonl.gz`；
* 候选 artifacts：`experiments/she_agentdojo_run1/cand_e*/`（含 `candidate.json` 提案与诊断/路由）；
* 接受后的新 anchor：`experiments/she_agentdojo_run1/H_best_e*/`；
* 结果表：`experiments/she_agentdojo_run1/result_table.json`（train / test-dev / test-heldout / plain × {H0, SHE-seed, SHE-evolved}）。
