# 环境与仓库策略

## 为什么运行环境不放项目里

`vLLM + torch` 的运行环境约 **8–12 GB**；venv 里还全是**绝对路径**（`pyvenv.cfg`、`bin/*` 的 shebang），
目录一移动就失效（上一个工程 `safety-codesign/.venv` 就吃过这个亏：搬目录后 `.venv/bin/*` 全废）。

因此约定：

| 东西 | 放哪 | 进不进仓库 | 体积 |
|---|---|---|---|
| 运行环境（vLLM/torch） | **项目外**：`/mnt/shared-storage-user/ai4good1-share/majiachen/.venvs/fmr-vllm`（组共享卷，2026-10-14 指定；实测可用 782 GB） | ❌ | 8–12 GB |
| `data/`（11 个 benchmark 检出） | 项目内 | ❌（`.gitignore` 排除，可重新克隆） | 数十 GB |
| `evolve/harness/upstream/`（EvoSafeHarness 等） | 项目内 | ❌（同上） | ~10 MB |
| `.pydeps/`（deepdiff / email-validator） | 项目内 | ❌（`env_setup.sh` 一键重建） | 几 MB |
| `.shims/`（litellm/groq/ollama/together/mistralai/vertexai/tenacity 单文件桩 + `inspect_ai/`） | 项目内 | ✅ | 几十 KB |
| 模型 SDK 子模块桩（anthropic / openai / cohere / google.genai） | **代码**：`src/coevolve/sdk_stubs.py` 的 meta_path finder（`install()` 早于 `import agentdojo`） | ✅ | 几 KB |

**为什么 SDK 桩必须是代码而不是 `.shims/<pkg>/` 目录**：AgentDojo 会 `import a.b.c` 形式的子模块
（如 `from anthropic.types.text_block_param import TextBlockParam`），放一个 `types.py` 会报
`'anthropic.types' is not a package`。finder 的规则是：先在 sys.path 找真包、找到就放行，
找不到才合成占位模块并挂 `__path__` 继续合成更深子模块；小写名字（`types`/`_types`/`chat`/`errors`…）
解析成子模块，大写名字（`Anthropic`/`Schema`/`NOT_GIVEN`…）解析成占位类。（2026-10-15 修）
| 切分清单 / Δ 库 / 文档 / 代码 | 项目内 | ✅ | 小 |

**空间说明**：2026-10-14 两次实测差异很大（先 30 GB、后 782 GB 可用）——共享卷是组内共用、波动大。
装 venv 前先 `df -h` 看一眼；`.venvs/` 在项目目录之外，不会被项目仓库收录。

## 重建

```bash
bash evolve/harness/scripts/env_setup.sh          # 建 venv + 小依赖 + 装 vLLM + 预检
INSTALL_VLLM=0 bash evolve/harness/scripts/env_setup.sh   # 不装 vLLM（走 transformers 兜底）
```

**注意两条实测教训**：
1. `pip install vllm` 要跑很久（数 GB 下载 + 共享卷 virtiofs I/O 慢，建 venv 本身就要几分钟），
   必须让进程一直活着——后台 `&` 会被会话回收杀掉（实测被杀过一次），用 `setsid nohup ... &` 或前台跑；
2. 别用 `pkill -f "pip install vllm"` 清理旧进程——它会匹配到你自己的命令行并把自己杀掉（实测）。按 PID 精确处理。

## 服务栈两条路

| 路径 | 条件 | 形态 |
|---|---|---|
| vLLM | 装好且注册 `qwen3_5`（`preflight_serving.py` 会告诉你） | 常驻/作业内起服务 + 并发池（连续批处理，功率上得去） |
| transformers 5.8.1（系统自带，**原生支持 qwen3_5**） | 无需安装 | 离线批处理（吞吐低，按 `(episode, step)` 打包成密集批次） |
