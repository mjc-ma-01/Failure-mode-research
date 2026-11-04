# 失败归因分类：J0–J3（所需判断层级）

状态：v2 提案，取代 `FAILURE_LABELING.md`（v0）里的 H1–H4 与 `FAILURE_LABELING_EVIDENCE.md`
里的 W/P/C/S/H/X。**只用可信数据推导**：Agent-SafetyBench 官方任务、AutoControl-Arena
`configs/scenarios/benchmark` 官方场景、其他公开 bench。

> **可计算定义见 `FAILURE_CHECKERS.md`（规范性）**：J0–J3 各自的谓词文法、反事实判定、
> 探针实验、见证格式与可信链都在那里；本文只负责"类别是什么、为什么这样分"。

## 1. 数据可信边界（先划清，再分类）

| 来源 | 是否纳入归因 | 说明 |
|---|---|---|
| Agent-SafetyBench 官方 `released_data.json`（2000 条）+ 我们的 3200 条采样（gpt-4o-mini × base/unprotected/safeharness/she，judge=gpt-4.1） | ✅ | 任务与标签是官方的；judge 是独立强模型 |
| AutoControl-Arena `configs/scenarios/benchmark`（7 类 71 个官方场景） | ✅ | 官方场景，含 `design_specification` / `technical_specs` / Hacking Point |
| AutoControl-Arena 其他 risk 类型（benign_semantic_* / capability_* 等） | ❌ | 再造数据，不纳入失败归因 |
| `capability_risk_agent` 的人工场景集 | ❌ | 自建，仅作方法参考 |
| `safety-codesign` 的 3264 条 episode（自建四域环境） | ❌ | 自建环境，仅作工程参考 |
| AgentDojo / AgentHarm / impossiblebench / machiavelli / propensity / AgentSecurityBench / AgentDyn / agentic-misalignment / Agentic-Upward-Deception | ✅（二手） | 用于验证分类覆盖面，不用于估计占比 |

## 2. 轴：挡住这次失败所需的**最低判断层级**

一条轨迹只取**最低的充分层级**（最便宜的充分干预），因此标签互斥、沿一根阶梯有序。

### 2.0 一眼版（判断顺序，越靠前越便宜）

1. **J0｜手滑类**——**数一下就知道**：同一个工具连按 3 次、参数格式不对、用了不存在的工具、步数用完。
2. **J1｜对不上账类**——**拿它的动作和当时的记录对一下就知道**，五张账：
   版本账（拿着旧信息就动手）、权限账（这件事不在允许范围里）、来源账（用的信息不是从该读
   的地方读来的）、前置账（该先做的读/确认没做）、说法账（说"完成了"但记录里没做）。
3. **J2｜该不该做类**——**对表对不出来，得看懂内容才知道**：金额算错、这话不该说、
   结论没依据、在钻评估空子。
4. **J3｜做不出来类**——**把正确做法直接告诉它，它还是做不对**。

**一眼分清 J1 和 J2（只需记这一句）**：

> 问：在同样的工具、同样的参数名、同样的当时状态下，有没有一个**合法**动作和它长得一模一样？
> **有 → J2**（说明没有规则能把它和正当行为分开，只能靠理解内容）；
> **没有 → J1**（有一条规则能把它挑出来）。

两个例子：

- 危险动作是"拿着**过期版本号**退款"，而所有合法退款用的都是当前版本号 → 对表就能挑出来 → **J1**；
- 危险动作是"退款 500 元"，而合法的退款也可能正好是 500 元（换个单子、同样状态）→ 长得一模一样 → **J2**。

**为什么值得信**：每层只要一种检查——数数（J0）、对账（J1）、看内容（J2）、给答案（J3）。
前两种机器一定算得出来；后两种我们**改成做实验**：J2 用"补全信息后重跑"，J3 用"直接告诉它
正确做法后重跑"。标签是实验读数，不是某个 LLM 的意见。

| 标签 | 含义 | 判据 | 见证 |
|---|---|---|---|
| **J0 机械层** | 不需要任何内容理解：计数、格式、顺序、schema | 重复调用、参数不合 schema、非法工具、超预算、顺序违规 | 计数/格式日志 |
| **J1 状态层** | 需要读运行时**状态事实**，但不需要理解内容含义：版本与新鲜度、权限与范围、取值 provenance、前置动作是否完成、幂等/可逆、声明与执行台账是否一致 | 存在只读状态事实的谓词 σ₁，能拦下它且**放行所有同签名合法动作** | 该谓词 + 它放行的全部合法动作集合 |
| **J2 语义层** | 必须理解内容与意图：这句话是否有证据、金额/目的/范围是否与任务语义一致、是否误导、是否在钻评估空子 | 把 J1 特征全部对齐后，仍存在**必须放行**的合法孪生 | 该孪生（任务 id + 步号） |
| **J3 能力层** | 判断齐备也做不到：知识/推理/规划能力不足，或需要长程一致性 | 在信息、状态、语义判断都齐备的条件下仍失败（或存在 reference solution 而模型达不到） | reference 轨迹，或重复尝试的失败记录 |

判据的机械形式（线性、无搜索）与复杂度见 `FAILURE_CHECKERS.md` §3：J1 = 与所有合法孪生
在白名单状态事实上都不同；J2 = 存在一个在所有维度上都相同的合法孪生。每步只做几十次
整数比较，**不需要枚举谓词、不需要 LLM**，与 F3"重复 ≥3 次"属同一类检查。

映射到杠杆：**J0 + J1 = harness 的确定性地盘**（中间件 + 检查）；**J2 = 模型**（或 harness 内的
LLM 监控＝第二意见，需单独实验、匹配推理预算）；**J3 = 模型能力**（训练/规模）。

移出这一维、作为**附件**记录的东西（它们不是失败类型）：
`action_bearing`（这一步有没有工具动作——没有动作就没有钩子可用）、
harness 摩擦/干预致害（这是 harness 缺陷，用配对重复判定，单独报告）、
危害类别与严重性、步号与工具名。

## 3. 从可信数据推导

### 3.1 Agent-SafetyBench 官方 10 种 failure mode → J 层

（2000 条官方任务的多标签计数）

| mode | 官方含义 | 次数 | J |
|---|---|---:|---|
| 6 | 工具参数错误 | 122 | **J0** |
| 2 | 信息不完整就调工具 | 257 | **J1** |
| 3 | 未取得完整信息就调工具 | 77 | **J1** |
| 4 | 忽略已知约束 | 333 | **J1** |
| 8 | 漏调必要工具 | 79 | **J1** |
| 9 | 过度信任工具结果、未验证 | 358 | **J1** |
| 1 | 直接生成有害内容、无工具调用 | 392 | **J2** |
| 5 | 忽略隐含风险 | 421 | **J2** |
| 7 | 调用有已知安全/法律问题的工具 | 131 | **J2** |
| 10 | 未过滤/排序工具结果 | 124 | **J2** |

按层汇总（任务数，多标签）：**J0 6.1%（122）、J1 50.1%（1003）、J2 51.5%（1029）、J3 0%**。

### 3.2 AutoControl-Arena 官方 benchmark 场景 → J 层

| 类别 | 场景数 | J | 依据 |
|---|---:|---|---|
| specification_gaming | 11 | **J2** | "字面合规、意图违背"（如把未完成项标记完成以刷指标） |
| covert_whistleblowing | 9 | **J2**（条款式违规部分可 J1） | 违反明文规则 + 隐瞒包装 |
| evaluation_awareness | 7 | **J2** | 察觉被评估就改变行为，运行时事实不可分 |
| instrumental_convergence | 16 | **J2–J3** | 关机抵抗、资源夺取等长期策略 |
| oversight_evasion | 9 | **J2** | 对抗监控本身 |
| capability_misuse | 10 | **J2** | 有能力而滥用（意图层） |
| strategic_misalignment | 9 | **J3** | 长程策略与价值取舍 |

**整个 benchmark 几乎全落在 J2/J3**——这正是模型侧的地盘。

### 3.3 其他公开 bench → J 层（覆盖面校验）

AgentDojo（提示注入）→ **J1**（provenance/污点：来源与指令权限可查）；
AgentSecurityBench（攻防）→ **J1**（权限与参数检查）；AgentDyn（分布漂移下的防御）→ **J1**；
Agentic-Upward-Deception（上报失实）→ **J1**（声明 vs 执行台账可机械核对）；
AgentHarm（恶意请求）→ **J2**；impossiblebench（不可能任务下拒绝作弊）→ **J2–J3**；
agentic-misalignment（勒索/泄露）→ **J2**；machiavelli、propensity → **J2–J3**。

## 4. 三个可检验的洞察

1. **J1 是最大的未开发地带。** ASB 官方任务里约一半的失败落在 J1——本该被"只读状态事实"的
   检查挡住。而实测里 harness 只拦了很少：SafeHarness 5 个动作 / 3 条轨迹（0.6%），
   SHE 118 个动作 / 108 条轨迹（13.5%）。**harness 的收益空间主要在这里，不在 J2。**
2. **两个可信数据源在同一根轴的两端互补。** ASB 偏 J0/J1（可检查、可工程化），
   AutoControl benchmark 偏 J2/J3（只有模型能给）。这为"什么归 harness、什么归模型"
   提供了实证分界，而不是立场之争。
3. **声明类失败属于 J1，不是 J2。** "声称完成但无证据"可以对着执行台账机械核对
   （状态事实），所以它应该在 harness 侧被吃掉——这也是最容易做出可见收益的一类。

**可证伪的预测**：进化 harness 只能压缩 J0+J1 的占比，J2/J3 不动；SFT/RL 才能压 J2，
而 J3 需要更强的训练或更大的模型。若实验显示 harness 能压 J2，说明我们的 σ₁ 定义太粗；
若 SFT 压不动 J2，说明数据或训练配方不足。这与参考论文（arXiv:2610.11655）的形态一致
（F2/F3 被 harness 消掉、F4 不动）。

## 5. 与 F1–F4 的对应

| 参考论文 | 本文 | 差异 |
|---|---|---|
| F3 执行控制 | **J0** | 一致 |
| F1 证据（可核对部分） | **J1** | 拆出"可验证事实"这一层 |
| F1 证据（判断部分）+ 内容 | **J2** | 明确为内容/意图判断 |
| F4 规划能力 | **J3** | 一致 |
| F2 harness 摩擦 | 移出轴外 | 不是失败类型，是 harness 缺陷（附件） |

## 6. 用哪个 harness 采这些轨迹

| 数据集 | 实际用的 harness | 可信度 |
|---|---|---|
| ASB 我们的 3200 条 | 条件 = base（无工具）/ unprotected / **SafeHarness** / **SHE**；judge = gpt-4.1 | harness 是真实实现；但**只有 gpt-4o-mini 一个模型、每格单次采样**——无法分离方差 |
| AutoControl 再造数据的结果 | SafeHarness（bridge） | 场景不可信 → 不纳入 |
| safety-codesign | 自研协议（evidence/protocol binding） | 环境自建 → 不纳入 |
| EvoSafeHarness | 被进化的对象 = DTAP 原生 agent 栈（`dt_arena` + MCP 工具服务器 + 3 个 SDK 适配）+ overlay（`HookManager` + Defense 加载器）；种子 = `dtap_def_v0`（空防御）；warm start = CaMeL / DRIFT 移植；可编辑面 = system prompt + 两个工具钩子 | 代码真实；但只覆盖 DTAP 的 3 个领域 |

**建议**：

1. **分类建在无防护臂上**（unprotected），否则标注的是被 harness 过滤后的分布，存在选择偏差；
   harness 臂只用来测"能吃掉哪一层"。
2. **采轨迹用性能最好的现成 harness：SHE**（ASB 上 unsafe 19.9% vs 无防护 29.5%，带拦截理由，
   自带 `data/agent_safety_bench/` 固定划分与 evolution 代码）。SafeHarness 明显更弱
   （23.4%、仅 5 次拦截）。
3. **要做"进化"**：SHE 自带 evolution（`scripts/run_safety_bench_evolution.sh`）；
   EvoSafeHarness 提供循环范式（Designer → Criticizer → Cascade → Analyzer + 分级门控），
   但移植到 ASB 需要重写 runner，且它的可编辑面偏窄。
4. **每个（任务 × 条件）至少重复 3–5 次**，否则 J1/J2 的差异与运行方差分不开。
5. 先用 J 阶梯在**现有 ASB 3200 条**上做一次试标：把每条失败轨迹标成 J0/J1/J2，与官方
   failure mode、以及 harness 是否拦下做交叉表——这能在不跑新实验的情况下检验分类是否可用。
