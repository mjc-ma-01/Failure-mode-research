# GPU 利用率：实验室口径与我们的判断

依据：《实验室算力资源精细化管理宣贯》（2026-09-03）。标定脚本
`evolve/harness/scripts/calibrate_util.py`（已按实验室口径改写）。

## 1. 实验室怎么算利用率（原文定义）

> **利用率 = (实际功率 − 静息功率) / (额定功率 − 静息功率)**，门槛线 **40%**；
> H200 为 **352W**、A800/A100 为 196W；只考核**已占用卡**；统计是**周期内长期均值**
> （示例窗口 [T-15, T-1]）。

这是**功率口径**，不是 nvidia-smi 的 `utilization.gpu`。对 H200 反推：静息 ≈120W、额定 700W →
0.40×580+120 = **352W**，与文件数字吻合。

文件里三条与我们直接相关的判断：

1. **"分散推理任务"被点名**：*"团队自行部署模型推理服务，因 H200 推理性能极强，独立小场景运行
   推理必然浪费资源"*。
2. **情景三"推理场景"**：*"modelset（在线服务）在 0–20%、20–40% 利用率档位大量分布……推理任务的
   计算密度远低于训练，GPU 大部分时间在等待请求"*。
3. 未达标处理：第四象限"低效算力回收"；预算按**卡时（GPU-hours）**核算。

另：`013--rjob分布式训练任务.pdf` 是 rjob 使用手册，**没有**利用率阈值；若 rjob 实际按 50% 执行，
H200 对应 **410W**。脚本默认目标线取 50%（`--target-util 0.50`），同时报告官方 40% 线。

## 2. 结论：单会话串行必然不达标；必须让功率持续高

- 单序列 decode 是显存带宽瓶颈（19GB 权重每 token 读一遍）→ 功率通常 200–300W；
  再叠加步间空档（CPU 跑工具/检查），长期均值会掉到 200W 上下 → 利用率 ≈15–25%，
  **连 40% 线都够不到**。
- 提高功率的唯一有效办法是**让单位时间真实计算量上去**：大 batch 连续批处理、更长的 prefill、
  judge 等请求并入同一队列。

**本模型的有利条件**：Qwen3.5-9B 是混合注意力（32 层里只有 8 层全注意力，`num_kv_heads=4`、
`head_dim=256`）→ 每 token KV ≈32KB，100k tokens ≈3.3GB。19GB 权重 + 32k 上下文在 141GB H200 上
可把 `--max-num-seqs` 开到 64–128，**并发上限不在显存**——这是把功率做上去的前提。

**一个反直觉点**：`--enable-prefix-caching` 提高吞吐，但每步只算增量 → **降低功率**。
对吞吐友好、对功率口径不利。标定时两种配置各测一次，取"既过线又不浪费卡时"的组合。

## 3. 会拖低长期均值的三个坑（功率口径）

| 坑 | 影响 | 对策 |
|---|---|---|
| 并发 episode 数不足 | 请求队列空 → 待机 ≈120W，直接拉低均值 | 并发 episode ≥32，队列常满；宁可少开卡 |
| 模型加载/启动（19GB 从 gpfs 读） | 加载期 GPU 近静息，作业越短占比越大 | 作业跑足够久（加载 <5% 时长）；加载与预热重叠 |
| judge/评估单独占卡 | 判分时 victim 近静息 | 判分并入同一服务队列，或同卡再起进程 |

## 4. 标定流程（开跑前的 gate）

```bash
# 1) 起服务（一张卡）
bash evolve/harness/scripts/serve_vllm.sh 8000

# 2) 扫并发：输出稳态功率 / 实验室口径利用率 / SM 利用率 / 吞吐 / 延迟
python3 evolve/harness/scripts/calibrate_util.py \
  --base-url http://127.0.0.1:8000 --model qwen3.5-9b \
  --concurrency 1 4 8 16 32 64 --seconds 60 --warmup 10 \
  --prompt-tokens 2000 --max-tokens 256 --target-util 0.50

# 3) 对照配置：去掉 --enable-prefix-caching 再测一次（功率 vs 吞吐的取舍）
```

判定规则（写进协议）：

- 取**满足"实验室利用率 ≥ 目标线"的最小并发度**跑正式实验，作业期间队列保持非空；
- 若到 64 并发仍不达标，按顺序补救：① 提高并发与 `--max-num-seqs` → ② 关 prefix caching
  （用算力换功率）→ ③ judge 并入同一服务 → ④ 组采样 `n=4` → ⑤ 离线批处理把
  `(episode, step)` 打包成密集批次（放弃常驻服务，改为"短而密"的作业）；
- **未达标不启动正式作业**（否则被判第四象限、收回算力）。

## 5. 与实验框架的衔接

- 并发最小单位是 episode：`run_pair()` 里 `(task, seed, Δ)` 互不依赖，客户端加一层并发调度即可
  让请求队列常年非空。
- token/延迟/重试已在 `VLLMServerModel.usage` 记账，直接并入协议成本栏；实验室按卡时核算，
  两者一起报。
- 标定与 σ 一样是**开跑前 gate**：利用率不达标，实验不开始。

## 6. 形态选择：批量（作业内起服务），不是长期常驻

实验室按**分配周期内的长期均值**考核，且明确点名"占位空转"。因此判据是：
**卡被占用的整段时间里，有多大比例在有队列**——而不是"服务本身能跑多满"。

| 形态 | 长期均值 | 结论 |
|---|---|---|
| 常驻服务（跨天/跨周） | 取决于使用率，通常最低 | ❌ 正是文件里点名的低效场景 |
| 短时交互服务（分钟级调试） | 短窗内高，摊销小 | ✅ 仅用于调试，调完即退 |
| **作业内起服务 + 并发池** | **最容易持续达标** | ✅ 正式实验一律用这个 |

作业时长按工作量反推（示例：210 任务 × 3 种子 × 5 臂 ≈ 3,150 episode ≈ 1.9 万次生成
≈ 570 万输出 token → 单次 sweep 约 1.5–3 小时），模型加载 2–3 分钟只占几个百分点。

实现：

```bash
# 一个作业：起服务 → 健康检查 → 并发 sweep（全程采样功率/队列）→ 关服务
bash evolve/harness/scripts/run_sweep.sh 8000 32 0 1 2
# 离线自检（无卡，不需要服务）
python3 evolve/harness/scripts/run_pair_sweep.py --model scripted --limit 1 --seeds 0 1 2
```

`run_pair_sweep.py` 会输出并落盘三样东西：转移表、**队列占用采样**
（`nonempty_frac` 应接近 1）、**作业全程功率与实验室口径利用率**（`lab_util_pct`）。
后者就是提交正式作业前的自检结果。

## 7. 服务栈结论（2026-10-14 预检）

- 本机 **未装 vLLM**；`pip install --dry-run vllm` 解析成功 → **vllm 0.31.0**，
  但它会**连带升级 torch（2.12→2.13）与 transformers（5.8.1→5.17.0）**。
  → 必须装进**项目内 venv**，不要动全局环境：

```bash
cd /mnt/shared-storage-user/ai4good1-share/majiachen/Failure-mode-research
python3 -m venv --system-site-packages evolve/harness/.venv
evolve/harness/.venv/bin/pip install -U pip
evolve/harness/.venv/bin/pip install vllm            # 数 GB，含 torch 2.13
evolve/harness/.venv/bin/python evolve/harness/scripts/preflight_serving.py   # 复检 qwen3_5 是否注册
```

- **兜底路径已确证可用**：系统 transformers 5.8.1 原生带 `qwen3_5`
  （`transformers/models/qwen3_5/`，已注册进 `modeling_auto`）→ 即使 vLLM 装不上/不认这个架构，
  也能用 transformers 后端（吞吐低，按离线批处理形态跑）。
