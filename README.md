# Failure mode research

研究 agent 在**正常任务**（无恶意用户、无攻击输入）中的失败模式，回答一个分工问题：

> 哪些风险适合由 harness（执行侧的检查与协议）挡住，哪些必须让模型自己学会？

同一个失败模式，本项目用两条方法各验证一遍：

| 方法 | 改什么 | 现状 |
|---|---|---|
| A. Evolve harness | 只改 harness，模型权重冻结 | 骨架已搭好，见 `evolve/harness/` |
| B. Model 侧（SFT / RL） | 改模型权重，harness 固定 | 待整理，见 `evolve/policy/` |

## 主流程

```text
data/ 下各 bench 任务
   |  1. 统一加载成同一种任务格式
   v
Qwen3-8B（load ckpt 加载本地权重）
   |  2. 基线测试：记录失败模式，以及 harness 拦没拦住
   v
失败证据
   |  3. evolve harness：候选协议 -> 搜索集验证 -> 接受 / 拒绝
   v
进化后的 harness
   |  4. 在 sealed 测试集上复测，对比进化前后
   v
结论：哪些失败模式被 harness 消掉，哪些必须回到模型侧
```

## 目录导览

| 目录 | 作用 | 说明 |
|---|---|---|
| `data/` | 各公开 bench 的原始数据与代码 | 只读参考，不修改上游仓库 |
| `evolve/harness/` | harness 进化（冻结模型，只改协议） | 含论文代码 `upstream/EvoSafeHarness` |
| `evolve/policy/` | 模型侧更新（第二部分） | 先留出，只放占位说明 |
| `docs/` | 研究方案与路线图 | `ROADMAP.md` 是总计划 |
| `figures/` | 论文配图 | |
| `external_harnesses/` | 外部 harness 源码 | SafeHarness（本项目适配 fork）/ SafeHarbor / SHE，以 submodule 固定 |
| `archive/` | 早期探索代码 | 已完成使命，保留备查 |

## 路径与共享卷

本项目的**真实位置**是共享卷：

```text
/mnt/shared-storage-user/ai4good1-share/majiachen/Failure-mode-research
```

当前工作路径 `/mnt/shared-storage-user/majiachen/Failure-mode-research` 指向这里。
备份、打包、`rsync` 请用真实路径（否则默认只复制链接本身）。共享卷剩余空间紧张，
写大文件前先确认余量。

## 当前状态

- 第一部分（harness 进化）：目录与论文代码已就位，评测链路待实现，见 `docs/ROADMAP.md`。
- 第二部分（model 侧）：按计划先留空。
- SafeHarness 适配保存在 fork 的 `failure-mode-integration` 分支；AutoControl、
  AgentSecurityBench 与 Agentic-Upward-Deception 的正式实验包见
  `experiments/noharness_vs_safeharness_adapted_no_llm/`。
- SafeHarbor（arXiv:2605.05704）已固定到 `external_harnesses/SafeHarbor/`；方法、官方结果及
  AutoControl / SecurityBench 案例映射见 `docs/SAFEHARBOR_2605.05704.md`。
