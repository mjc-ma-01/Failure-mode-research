# refs

外部参考论文的本地副本（PDF + 网页副本，便于检索）。引用时请按 arXiv 条目。

| 文件 | 论文 | 为什么放这 |
|---|---|---|
| `harness-evolution-ceiling-2610.11655.pdf/.html` | *Harness Evolution Hits a Ceiling: When Weight Training Should Begin*（arXiv:2610.11655，2026-10-08） | 给出"先进化 harness、再决定何时训权重"的判据，与本项目的分工问题直接对应 |
| `safeharbor-2605.05704.pdf` | *SafeHarbor: Defining Precise Decision Boundaries via Hierarchical Memory-Augmented Guardrail for LLM Agent Safety*（arXiv:2605.05704v3，2026-07-23） | 新的层级记忆式安全 harness；官方代码固定在 `../../external_harnesses/SafeHarbor/` |

`safeharbor-2605.05704.pdf` 的 SHA-256：
`b29703c59344c9054c8a52e994ee42712380aa6e63927489889e08db8c6ca896`。

## 2610.11655 要点（供快速回查）

- **harness 定义**：DeepPlanning 的种子 harness = 状态台账 + 退出闸门 + 中途 checkpoint + 四道硬阻断；**可编辑面** = prompt 文件、策略参数、middleware、工具。
- **进化协议**（§4.2）：每轮 48 个 dev 任务 × 4 rollouts → 证据包（分数、健康率、F1–F4 计数、过程指标、最差案例）→ 提案模型出 **2 个候选编辑**（各带 manifest 与回滚条件）→ 每个候选 4 rollouts 对比当轮 anchor，house rules 拒绝（均值跌 >0.02、健康率跌 >0.05、未提交/重复调用率涨 >0.05）→ 留优者，**重新测 fresh anchor**。4B 跑 13 轮 / 26 候选，9B 跑 5 轮 / 10 候选。
- **失败分类 F1–F4**（§3.1，确定性判定，按首个触发信号）：
  - F1 证据：≥半数事实声明无出处，或带着未解决项过退出闸门；
  - F2 harness 摩擦：强制解锁 checkpoint、≥10 次调用被挡，且分数低；
  - F3 执行控制：同一调用重复 ≥3 次、用掉 ≥90% 步数、或被 harness 终止；
  - F4 规划能力：以上都不触发，交了计划但分数 <0.5。
  - 另记 delivery rate 与 quality among delivered，总分 = 两者乘积。
- **结果**：4B 0.156→0.292（held-out +0.133），9B 0.305→0.390；增益全在 F2/F3，**F4 从不下降**（4B 10%→28%）。
- **消融**（§6.1）：给能力的组件（台账、lessons、发明的工具）贡献几乎全部增益；执行类组件（退出闸门、checkpoint、硬阻断）基本在噪声内。
- **天花板归因**（§6.2）：证据包优先展示干预类过程指标，**从未把 scorer 的失败构成聚合进去**；作者明说这是该循环证据包的性质，不是 harness 进化的普遍性质。
- **权重训练**（§4.3、§5.2）：LoRA 训在**进化后 harness** 的轨迹上（每任务 8–12 rollouts，按阈值留最好 3 条；只对 assistant 输出算 loss；rank 32、dropout 0.05）。只用 adapter 在种子 harness 上 +0.126/+0.131；叠在进化 harness 上 4B 再加 +0.082、9B 互相替代。**安慰剂对照**（打乱 assistant 输出）低 0.158/0.227。
- **可训性判据**（§5.3）：改"模型写什么"的增益能训进权重；改"模型看到什么"的增益留在 harness（WebArena-Lite 上 adapter 完全不额外贡献）。
- **诊断流程**（§7）：先测噪声底 → delivery、quality、F1–F4 构成 → 分支：交付分数 <~0.18 不训；delivery 未饱和或 F3 主导 → 进化 harness；delivery 饱和且 F4 主导 → 训权重。
