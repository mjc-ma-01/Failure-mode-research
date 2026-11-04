# External harness repositories

第三方 harness 不复制进主仓库历史，而由 Git submodule 固定到精确 commit。

| 本地路径 | 仓库 | 固定 commit | 用途 |
|---|---|---|---|
| `SafeHarness/` | [`mjc-ma-01/SafeHarness`](https://github.com/mjc-ma-01/SafeHarness), branch `failure-mode-integration` | `bf2ea55ecc76073af3cea92501c5e39605402dfb` | 本项目适配 fork；供三个正式 benchmark 的项目侧 runner 共用 |
| `SafeHarbor/` | [`ljj-cyber/SafeHarbor`](https://github.com/ljj-cyber/SafeHarbor) | `4aa2be3bce7117739950b0de8ad4a5cebd1f81d7` | SafeHarbor 官方实现 |
| `SHE_official/` | [`RainbowQTT/SHE`](https://github.com/RainbowQTT/SHE) | `0c656460d9d8acdf406a2271d657f7a7b60bb255` | SHE 官方实现 |

EvoSafeHarness 位于 `../evolve/harness/upstream/EvoSafeHarness/`，同样作为
submodule 固定到官方仓库 commit
`98a4a96d61f2b6e040c1f677864073eabaef5311`。

## SafeHarness 适配的边界

fork 中保存可复用的 SafeHarness engine 修改和 AutoControl 格式桥接。它不是仅供
AutoControl 使用：AgentSecurityBench 与 Agentic-Upward-Deception 的项目侧 runner
也使用这个适配 engine。依赖特定数据切分的 runner、tier table、原始记录和报告留在
主项目，不复制到 fork。

详见：

- `SafeHarness/FAILURE_MODE_INTEGRATION.md`
- `../experiments/noharness_vs_safeharness_adapted_no_llm/`

## SafeHarbor

`SafeHarbor/` 对应论文
[*SafeHarbor: Defining Precise Decision Boundaries via Hierarchical Memory-Augmented
Guardrail for LLM Agent Safety*](https://arxiv.org/abs/2605.05704)。

当前固定版本的 smoke tests 可运行，但官方预构建 pickle 与当前 loader 不兼容：
pickle 缺少 loader 需要的 `embedding_model`，projected centers 和 benign exemplars
也为空。因此本项目记录了该问题，没有静默修改官方源码，也没有宣称 AutoControl 或
AgentSecurityBench 上的 SafeHarbor 结果。详细审计见
`../docs/SAFEHARBOR_2605.05704.md`。

## 克隆主项目后

```bash
git clone --recurse-submodules <main-repository-url>
```

若已经普通克隆：

```bash
git submodule update --init --recursive
```

API endpoint 和 credentials 必须通过环境变量或本地未跟踪配置提供，不能提交到仓库。
