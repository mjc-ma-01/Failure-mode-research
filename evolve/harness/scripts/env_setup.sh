#!/usr/bin/env bash
# 一键重建运行环境。设计原则：**环境放在项目外**（仓库保持小巧；venv 含绝对路径，目录一移动就废）。
#
# 用法：
#   bash evolve/harness/scripts/env_setup.sh            # 默认装到 $FMR_VENV 或 ~/.venvs/fmr-vllm
#   FMR_VENV=/path/to/venv bash evolve/harness/scripts/env_setup.sh
#   INSTALL_VLLM=0 bash ...env_setup.sh                  # 只建 venv 与小依赖，不装 vLLM
#
# 目录约定：
#   FMR_VENV  运行环境（torch + vllm 等，约 8–12GB）——必须放项目外
#   .pydeps   AgentDojo 缺的两个小依赖（deepdiff / email-validator，几 MB）——留在项目内但被 .gitignore 排除
set -euo pipefail

# 运行环境放**项目外**（不进仓库）。默认放组共享卷（2026-10-14 用户指定；实测可用 782GB）。
FMR_VENV="${FMR_VENV:-/mnt/shared-storage-user/ai4good1-share/majiachen/.venvs/fmr-vllm}"
INSTALL_VLLM="${INSTALL_VLLM:-1}"

echo "[env] 项目根目录: $ROOT"
echo "[env] 运行环境将建在: $FMR_VENV （项目外，不进仓库）"

if [ ! -x "$FMR_VENV/bin/python" ]; then
  mkdir -p "$(dirname "$FMR_VENV")"
  python3 -m venv --system-site-packages "$FMR_VENV"
fi
"$FMR_VENV/bin/pip" install -q -U pip

echo "[env] 安装 AgentDojo 的两个小依赖到 $ROOT/evolve/harness/.pydeps"
"$FMR_VENV/bin/pip" install -q --target "$ROOT/evolve/harness/.pydeps" deepdiff email-validator

if [ "$INSTALL_VLLM" = "1" ]; then
  echo "[env] 安装 vLLM（数 GB，含 torch；请让本进程一直活着，或改用 setsid 脱离会话）"
  "$FMR_VENV/bin/pip" install vllm
else
  echo "[env] 跳过 vLLM；可先用系统 transformers 5.8.1（原生支持 qwen3_5）跑离线路径"
fi

echo "[env] 复检服务栈："
"$FMR_VENV/bin/python" "$ROOT/evolve/harness/scripts/preflight_serving.py"
