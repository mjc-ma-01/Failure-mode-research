# evolve/harness

冻结模型权重，**只进化 harness**，测量哪一类失败模式能被执行侧的检查与协议消掉。

> **实验框架已就位**：`FRAMEWORK.md` + `src/coevolve/`（已用真实 Agent-SafetyBench 环境跑通
> selfcheck）。分类从 "model+initial harness vs model+Δharness" 的配对转移里**实证**得出，
> 不预先按 risk 分类。

## 论文代码：EvoSafeHarness

`upstream/EvoSafeHarness/` 是论文
*EvoSafeHarness: Evolving Model- and Domain-Specific Harnesses for Securing Agents*
的官方代码（Li et al., 2026；JHU / NVIDIA / UW–Madison / UIUC / UC Berkeley；
[论文 PDF](https://andylinx.github.io/EvoSafeHarness/assets/EvoSafeHarness_paper.pdf)）。
核心主张一句话：**搜 harness，不训模型**（search the harness, not the model）。

| 概念 | 论文里的做法 |
|---|---|
| 对象 | victim model 冻结，逐 `(模型 × 领域)` 进化一套 defense bundle |
| harness 形态 | 一个目录：`BUNDLE.md`（策略与理由）+ `defense.py`（三个钩子 `system_prompt_transform` / `on_pre_tool_call` / `on_post_tool_call`）+ `__init__.py` + `parent.txt` |
| 搜索循环 | Designer 读失败轨迹写候选 -> Criticizer 独立上下文找茬（防过拟合）-> Cascade 分级打分 Stage 0→3 -> Analyzer 把失败整理成设计笔记 |
| 打分 | `score = utility% − ASR%`，另跑鲁棒性探针与过度拒绝探针 |
| 评测 | 冻结 held-out `test_subset100`（30 benign + 35 direct + 35 indirect），报 utility、ASR（直/间接分开）、gate_TP、gate_benign_FP |
| 环境 | 跑在 DTAP（DecodingTrust-Agent，arXiv:2605.04808）上，需 Docker 与 judge proxy；victim 在 `.env` 里选，不写死 |

上游的来源与依赖：DTAP 提供多领域红队平台与逐任务判分；CaMeL、DRIFT 作为
warm-start 种子与对比基线（DRIFT 与 EvoSafeHarness 同属 SaFo-Lab）；
搜索循环的 proposer 框架取自 Meta-Harness（Stanford IRIS）。

上游仓库结构：

```text
upstream/EvoSafeHarness/
  domains/<domain>/          finance · os-filesystem · telecom
    domain_spec.md           领域契约，同时就是给 proposer 的 prompt
    splits/                  冻结任务清单：stage1_smoke … stage4_wide, train, test_subset100
    defenses/_baselines/     种子 bundle：dtap_def_v0（无防御）、dtap_camel_v1、dtap_drift_v1
    overlay/、scripts/       叠加进 DTAP 的源码与 cascade / probe 脚本
  eval_platform/             held-out 对比平台（run / compare，输出 comparison.md）
```

## 与 SafeHarness 的关系

`SafeHarness`（arXiv:2604.13630，生命周期安全架构）保留在
`../../external_harnesses/SafeHarness`，作为**外部对比基线**，不复制进本目录。

## 外部基线：SafeHarbor（arXiv:2605.05704）

官方源码固定在 `../../external_harnesses/SafeHarbor`，论文和详细审计见
`../../docs/SAFEHARBOR_2605.05704.md`。它是“Safety Projector + 层级 Risk Tree +
禁止/良性例外规则注入”的 prompt-time proxy，和 SafeHarness 的 pre-tool hard hook
不是同一个执行面。

当前固定 commit 的发布 pickle 与 loader 不兼容，官方 `retrieve_query()` 尚不能直接跑通；
因此现在只登记为**源码已引入、结果待测**，不填造 AutoControl / AgentSecurityBench 成绩。
后续接入必须把原版 query-only 臂和 action-adapted 臂分开报告。

## 方法参考：Harness Evolution Hits a Ceiling（arXiv:2610.11655）

本地副本在 `../../docs/refs/`。它回答的正是本项目要问的分工问题：**什么时候该进化 harness、
什么时候该训权重**。三条直接改变我们做法的结论：

1. **证据包里必须聚合失败构成。** 那篇论文的循环停在 F4（内容类失败）上，作者自己归因：
   证据包优先展示"干预类过程指标"，而**从未把 scorer 的失败构成汇总给提案模型**——
   循环只能优化它看得见的东西。我们的 evidence package 必须显式包含 H1–H4 占比
   （见 `../../docs/FAILURE_LABELING.md`），否则会重犯同一个错误。
2. **可编辑面要放宽。** EvoSafeHarness 只让改 system prompt 和两个工具钩子；那篇论文的可编辑面
   是 prompt 文件、策略参数、middleware、工具。它的消融显示：**给能力的组件（状态台账、蒸馏出的
   lessons、发明的工具）贡献几乎全部增益，执行/合规类组件（退出闸门、checkpoint、硬阻断）
   基本在噪声内**。我们的 harness 定义不要只做成"拦截器"。
3. **训得进去的只有一类增益。** 被接受的编辑若改的是"模型写什么"，增益可以训进权重；
   若改的是"模型看到什么"，增益留在 harness。先读编辑触碰的面，再决定花不花训练预算。

## 相关论文（本地不存代码）

- **SafeEvolve**：*Harness-Policy Co-Evolution from Agent Experience for Safety
  Alignment*（arXiv:2609.02786，`MaoPopovich/SafeEvolve`）。它同时进化和策略，
  与 EvoSafeHarness 的"只搜 harness"是两条不同路线，可作为后续对比工作。
  需要时再拉代码，不要混进 `upstream/`。

## 我们的链路（待实现）

```text
load_ckpt(Qwen3-8B) -> 冻结 victim
        |
        v
data/ 各 bench 上跑基线 episode，记录：动作、观测、拦截、状态变化、独立危害判定
        |
        v
按预注册规则给每条轨迹打一个标签（H1–H4，见 ../../docs/FAILURE_LABELING.md）
        |
        v
harness 编辑器：可改 prompt / 检查与 middleware / 工具定义
（不改权限模型、不改任务真值、不改 reward、不改隐藏标签）
        |
        v
evidence package（分数、H1–H4 构成、干预日志、最差案例）
        |
        v
候选 bundle -> 搜索集分级打分 -> 过安全+效用门 -> 独立 dev 面板确认
        |
        +-- 被拒绝：回滚，保留 parent harness
        |
        v
held-out 测试集复测：对比效用 / 危害 / H1–H4 构成 / 拦截率 / 过度拒绝 / 成本
```

接口草案（先定名字，实现留到下一步）：

```python
def load_ckpt(model_dir: str, revision: str) -> Actor: ...
def run_episode(task: Task, actor: Actor, harness: Harness, seed: int) -> Episode: ...
def collect_evidence(episodes: list[Episode]) -> Evidence: ...
def propose_candidates(evidence: Evidence, parent: Harness, budget: Budget) -> list[Harness]: ...
def evaluate(harness: Harness, tasks: list[Task], actor: Actor) -> Metrics: ...
def accept(candidate: Harness, parent: Harness, dev: Metrics) -> Decision: ...
```

## 已验证的经验（来自上一轮实验）

这些是上一轮正式实验跑完后留下的约束，直接沿用：

- harness 候选**大概率会被"实测效用下降"否掉**，不要因为生成了候选就假定它有效。
- 旧回答的 token 不能冒充 on-policy 数据；任何权重更新必须用当前权重重新采样。
- 被拒绝的候选要留下记录（分数、拒绝原因），拒绝本身是结果。
- dev 面板只能做诊断；测试集封存，只在最后测一次。
- "语义判断只属于模型"不是前提：外部 LLM 监控器也能做语义判断，分工要靠实验定。

## 待办

- [ ] 把 victim 换成 Qwen3-8B（`load ckpt` 方式）；先确认 DTAP 是否支持自定义模型接入，
      不支持就先在 `data/` 上自建 runner，再对齐 EvoSafeHarness 的打分口径。
- [ ] **先预注册标签规则**（`docs/FAILURE_LABELING.md` 定稿）：σ 词表、H1–H4 判据、见证格式，
      在跑任何搜索之前冻结；再实现确定性 checker。
- [ ] 统一 `Task` / `Episode` / `Harness` / `Metrics` 数据结构定义。
- [ ] 从 `data/` 挑第一批 bench（建议先 Agent-SafetyBench + impossiblebench，各取几十条）。
- [ ] 实现候选生成 -> 搜索 -> 接受/拒绝闭环，evidence package 必须含 H1–H4 构成；
      记录预算（候选数、episode 数、GPU 小时）。
