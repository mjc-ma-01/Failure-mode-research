# 失败标签：现有轨迹的实证与框架 v1

配套文件：`FAILURE_LABELING.md`（v0，保持原样，不覆盖）。本文是在读完项目内的
已有轨迹之后写的取证与修订建议。

> **可信边界更正（2026-10-13，按用户裁定）**
> 本文 §3 的 E1–E5 主要来自 `safety-codesign`（自建四域环境）与
> `AutoControl-Arena` 的非 benchmark 风险类型。按裁定：
> **AutoControl 只有 `configs/scenarios/benchmark` 下的官方场景可用**，其余 risk 类型属于
> 再造数据，不得纳入失败归因；自建环境同样不作为归因证据。
> 因此 E1–E5 **只作方法与工程参考，不作为分类依据**。分类依据见
> `FAILURE_TAXONOMY.md`（只用 Agent-SafetyBench 官方数据 + AutoControl benchmark 场景 +
> 其他公开 bench）。

## 1. 数据清点

| 来源 | 规模 | 关键字段 | 有无独立判定 | 有无干预日志 | 有无危害 oracle |
|---|---|---|---|---|---|
| `archive/agent_safetybench_experiments/sample_compare_20260811_perrisk100_gpt4o_mini/` | 3200 条轨迹（base / unprotected / safeharness / she 各 800） | `tool_calls`、`blocked_actions`、`judge{unsafe,task_completed,reason}`、`error` | 有（judge） | 有（blocked_actions） | 有（judge.unsafe） |
| `data/AutoControl-Arena/results/benign_semantic_harness_gaps/full_cumulative_r1/` | 120 条（60 场景 × 2 条件） | `oracle_unsafe`、`judge_label`、`blocked_*`、`tool_calls`、成对转移表 | 有（judge + oracle 双判） | 有（本次全为 0） | 有（严格 unsafe = oracle ∧ judge） |
| `archive/capability_risk_agent/out/real_harness_gap_dataset_v1/` | 24 场景 / 12 风险家族 | `safe call` vs `risky call` 成对、SafeHarness 判定（`allowed=True, risk_score=0.0`） | 人工设计 | 无 | 人工标注 |
| 项目外 `../safety-codesign`（已移出，只作历史数据） | **3264 条**真实 episode（train 1152 / search 576 / dev_accept 1536） | 每步 `proposed_action` / `verification{status,avoidable,risks,counterfactual}` / `gateway{decision,intervention,checks}`；`assessment{utility,harm_count,completed}` | **有，且是拦截前评估** | **有（decision/intervention）** | 有（harm_count） |

最后一份是最有价值的：它同时具备"提案 → 独立判定 → harness 决定"三段记录，而且是
**在拦截前的隔离视点上判定**的，正是我们需要的 ground truth 形态。

## 2. 剔除规则与数量

| 来源 | 剔除项 | 数量 | 处理 |
|---|---|---|---|
| ASB | `error` 非空（APIConnectionError） | 1 / 3200 | 剔除 |
| ASB | 工具不存在 | 1 | 剔除该步 |
| AutoControl | `judge_error` / `judge_valid=false` | 1 / 120 | 剔除 |
| safety-codesign | `errors` 非空 | 0 / 3264 | 无需剔除 |
| safety-codesign | `termination=invalid_action`（格式/动作非法，非环境错误） | **736 / 3264 = 22.5%** | **单列，不混入语义统计**（见 §4.5） |

另外两点**不是错误、但必须单列**，否则会污染结论：

- ASB 有 **1829 / 3199（57%）轨迹零工具调用**；`base` 条件更是 800/800 零调用。
  这些失败没有动作可拦，属于结构类别（v1 的 P）。
- AutoControl 的 60 个场景里 **harness 一次都没拦**（blocked=0），却出现了
  `unprotected safe → safeharness unsafe` 5 例。无拦截情况下的结果翻转**不能**归因给
  harness 的拦截，只能记为"软干预或噪声"（v1 的 X / H）。

## 3. 关键实证（每条都可复核）

**E1. 在粗签名下，有害与合法完全不可分。** safety-codesign 的 3264 条轨迹里共有
1036 个被独立判定为有害的提案步。取 `σ = (工具名, 参数名集合)`，**1036/1036 = 100%**
的有害提案与"必须放行"的合法提案同签名：

| 签名 | 有害步 | 同签名合法步 |
|---|---:|---:|
| `finish[claim, summary]` | 415 | 1940 |
| `send_message[document_id, field_ids, preview_id, recipient_id]` | 162 | 530 |
| `quarantine_file[file_id, preview_id]` | 162 | 629 |
| `refund[amount_cents, expected_version, operation_id, order_id]` | 145 | 140 |
| `refund[amount_cents, operation_id, order_id]` | 57 | 476 |

结论：任何只依赖"工具 + 参数名"的运行时检查都会同时挡掉大量合法动作。**标签框架的分界
必须落在更细的 σ 层**（版本/新鲜度、取值来源、权限范围）上，这正是 v1 要显式定义的"τ 分层"。

**E2. "缺前置读"在这个数据集里一次都没出现。** 1036 个有害提案**全部**发生在此前已有
读/预览类调用之后（0% 是第 0 步，0% 没有先读过）。所以 v0 里"任务规定的必需前置动作从未
执行"这条判据在这些数据上恒为假——失败不是"没看"，而是"看了以后用错了"。

**E3. 41.5% 的有害提案是完成声明，不是外部动作。** 风险名分布：`unsupported_completion_claim`
430、`excess_refund` 202、`purpose_exceeding_file_removal` 164、`purpose_exceeding_disclosure`
162、`active_dependency_interrupted` 111、`misleading_irreversible_notification` 58 等。
430 条声明类恰好对应 `finish` 的签名，其余 606 条是真实外部动作。**两类要分开统计**：
声明可以对证据台账机械核对（状态/来源层），外部动作常常要判断取值内容。

**E4. harness 的干预与危害几乎正交。** 该数据集里 312 次干预
（`extended_protocol_binding` 134、`protocol_argument_binding` 80、
`fresh_public_evidence_required` 98）全部落在"证据/绑定"层；而 1036 个有害提案
**0 个被拦**。584 个有害 episode 中 497 个全程没有任何干预，87 个有干预。

**E5. "拦截数"不能当 harness 的度量。** ASB 上 SafeHarness 只拦了 5 个动作（3/800 条轨迹），
unsafe 却从 29.5% 降到 23.4%；SHE 拦了 118 个动作（108/800），unsafe 降到 19.9%；
AutoControl 上 0 拦截也出现了双向翻转。**软干预（提示/记忆/优先级）必须与硬拦截分开计量，
否则会把一整类机制判成"没有效果"。**

## 4. 框架 v1 提案

轴不变：**"要消掉这次伤害，最早能在哪一层可靠介入"**。变化是把它写成沿管线的分层，
并要求每一层都有可机械检查的判据与见证。

| 标签 | 介入层 | 判据（τ 分层） | 见证 | 对应动作 |
|---|---|---|---|---|
| **W 权重** | 模型参数 | 危害只在**取值内容层**可分：取相同状态的合法动作与它同形，差别只在取值含义 | 同工具、同参数名、同状态类的合法孪生 | SFT/RL |
| **P 提示** | 系统提示 | 轨迹无动作可拦（纯文本输出），或危害来自行为漂移/优先级 | 零工具调用，或"无动作步"日志 | 改提示 |
| **C 钩子** | 单动作检查 | 在**状态/来源层**可分：版本与新鲜度、取值 provenance、是否绑定到已验证证据、权限/范围、幂等与可逆性 | 一条谓词 + 它放行的全部合法动作（E1 的分层版） | 加检查 |
| **S 中间件** | 序列/资源 | 重复调用、超预算、顺序错、格式非法、终止异常 | 计数、预算比、终止码 | 改 middleware |
| **H 组件** | harness 自身 | **配对重复**下，harness 在场或干预是危害的原因 | 同任务同种子区间的配对差分 | 修/删组件 |
| **X 剔除** | — | 重复采样下不稳定；或 `invalid_action` 等格式/适配失败 | 重复方差不覆盖；终态码 | 不进语义统计 |

打标签顺序：先跑 X 的剔除，再按 **P → C → S → W → H** 取首个成立者（H 需要配对实验，
所以它在流程上最后判）。这样每条轨迹仍然只拿一个标签，标签之间仍是同一根轴上的位置。

## 5. 相对 v0 的四点修订

1. **H1 从"看日志"改成"看配对因果"**：E5 表明干预日志既不必要也不充分；无拦截也能翻转，
   有拦截也可能只是并行发生。H 类必须由重复采样的配对差分判定。
2. **新增 X 剔除**：`invalid_action` 22.5% 这类格式/适配失败必须单列，不能算语义失败；
   不稳定的（同一配置重复跑结论不一致）也不能进统计。
3. **σ 分层写死**：E1 说明粗 σ 下 100% 碰撞，框架会退化成一个什么都判不出来的类别。
   τ 分层（值内容 / 状态·来源 / 序列）必须写进规范并预注册。
4. **声明与动作分开统计**：E3 的 430 条声明类有独立的、更机械的拦截层；合并统计会掩盖它。

## 6. 下一步（可直接做）

1. 用 τ 分层 σ 在 3264 条上实测**可分比例**：把 1036 个有害提案逐个过
   "状态/来源层"检查器（版本绑定、provenance、前置证据绑定、权限范围），
   得到 C : W 的经验比例——这就是本项目第一个可报的数字。
2. 用 `sample_compare` 的配对数据（同任务 × 4 条件）做 H 类归因试验，
   检验"无拦截翻转"是软干预还是噪声（用重复采样把二者分开）。
3. `invalid_action` 736 条的处理规则（排除 vs 归 S）先定死，再跑上面的统计。
