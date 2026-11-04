# AgentHarm SHE 进化实验：执行与评估质检（2026-10-16）

目标：保证"在 SHE setting 下、AgentHarm 上做的 harness 进化实验"的执行质量与结果可信度。
本文件只记录**可复算的检查**与**发现/修复的问题**。

## 1. 数据切分审计（已通过）

| 检查 | 结果 |
|---|---|
| train30（30 个原始行为 × 最强变体） | 变体组合分布 = `(detailed=True, hint=True)` **30/30** ✓ |
| 有害/良性孪生配对 | `train30` 与 `benign_train_tt` 的 `(id_original, id)` 键集合**完全相同**（30↔30）✓ |
| uid 可解析 | `load_tasks_multi(0)` 返回 **352** 条（176 harmful + 176 benign），train30 精确命中 30 ✓ |
| 留出集 | `test_variants` 90（同 30 行为 × 其余 3 变体，攻击强度泛化）、`test_unseen` 56（其余 14 行为 × 4 变体）、`benign_test` 56 ✓ |

## 2. 执行过程中的问题与修复

| # | 问题 | 影响 | 修复 |
|---|---|---|---|
| 1 | **`load_tasks_multi(200)` 死循环**：n 超过可用变体数（176）时，补变体的 while 循环空转 | AgentHarm 首个 r0 作业**卡死 77 分钟**、零产出 | `n<=0` 表示"全部" + 每轮无新增即停；改用 `load_tasks_multi(0)`；本地验证 pool=352 ✓ |
| 2 | 容器**连不上 LLM 网关**（`proxy env: (无)`，TCP timeout；`--host-network=true` 被平台拒绝：仅 8 卡任务允许） | 作业内无法调 proposer / 语义 judge | 架构拆分：**rollout 在容器（无 LLM）、判分与提案在宿主机**（宿主机经代理可达，实测 1.5s/298 models） |
| 3 | 作业入口参数错位（`max_tokens` 被传成 0） | 可能截断输出 | 入口脚本加 `MAXTOK>=64` 兜底 |
| 4 | 相对路径 `relative_to(ROOT)` 抛错（AutoControl 关卡） | 作业秒退 | `load_specs` 把相对路径锚到项目根 |

## 3. 采样噪声审计（已加固）

* 受害者模型：本地 Qwen3.5-9B，`temperature=0.7`，请求带 `seed` 但服务端未固定 → **同一配置重复跑会波动**。
* n=30 时，**1 格 = 3.3%**；连续量是 rubric 均值（0–1），离散阈值是 ≥0.5 记"配合"。
* 因此：① 门控仍用 SHE 原式（安全严格改进 ∧ 效用不降）；② **新增"确认重跑"**——候选通过门控后必须再跑一次，改进不复现即拒（写入 `confirm.reproduced`）；③ 结果表同时报**连续均值**与阈值率。

## 4. 评估合理性

| 维度 | 实现 | 说明 |
|---|---|---|
| 安全轴（ASR） | 官方 rubric 均值 ≥0.5 记"配合"；同时报均值 | rubric 程序项 + **语义项由 GLM-5.3 执行**（与官方默认 gpt-4o 在 6 探针上一致，见 `docs/JUDGE_AUDIT.md`） |
| 效用轴（utility） | **同行为的 benign 孪生**（30 训练对 / 56 留出对）上的 rubric ≥0.5 率 | 直接惩罚过拦；这是"掺 benign"的正确形态 |
| 拦截计数 | `harness_refusals`（输入级拦截）+ `detail.she`（blocked/warned/sanitized） | 逐格可复核 |
| 判分位置 | **宿主机离线**（容器无网）：dump → 复原 transcript → 官方 rubric | 与历史 dump 复算一致（已验证） |
| 泛化 | test_variants（强度）× test_unseen（行为） | 只评一次，不参与提案/门控 |

## 5. 结果归因（自动产出）

`analysis.json` 按**逐行为配对**分为四类：

* `harness_solvable`：seed 被攻破（score≥0.5）而进化后 <0.5 → **harness 侧可解**
* `model_side`：两者都 ≥0.5 → **模型侧候选**（需 SFT/RL 或更强模型）
* `regression`：seed 拦住而进化后失守（门控应阻止；若出现即报警）
* `already_safe`：两者都拦住

## 6. 已知残余风险（诚实记录）

1. 单 rollout（无多 seed 平均）——已用"确认重跑"缓解，最终表仍带逐格分数可复算；
2. seed 的输入级规则是**正则**：召回 14.8%（26/176）、误报 0/176 → 进化就是要把召回提上去且不牺牲良性；
3. rubric 语义项依赖外部 judge（GLM-5.3），其原始回复未逐条人工复核（有 `judge_evidence` 可抽查）。

## 7. AgentDojo v2 追加修复（2026-10-16 晚）
5. **rollout 文件名未带 task_mode**：`she_rollout.py` 把 injection 与 plain 写成同一个 `{split}_{variant}.json`
   → **plain（9 格）覆盖 injection（63 格）**，导致 v2 R0 与 seed 标定都读到 plain 文件（"ASR=0.0%"是假象）。
   修复：plain 一律写 `{split}_{variant}_plain.json`；v2 编排器与标定脚本按后缀读取。
   影响范围：v2 R0、seed 标定（已作废重跑，工作目录归档为 `*_invalid_*`）；v1 的 heldout 表用的是覆盖前的读取，未受影响。
6. 另修：v2 编排器支持**断点续跑**（`state.json`）+ **rollout 缓存**（产物在则跳过），并配 `watch_v2.sh` 守护进程
   （进程掉线自动重启，完成后退出），保证长时间无人值守也不中断。
