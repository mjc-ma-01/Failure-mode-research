#!/usr/bin/env bash
# 把 vLLM 装完（可反复调用、幂等、带重试与完成标记）。
#
# 用法（**必须脱离会话启动**，否则会被回收杀掉）：
#   setsid nohup bash evolve/harness/scripts/install_vllm_bg.sh > /dev/null 2>&1 < /dev/null &
#
# 结果标记：$VENV/.install_state
#   OK-already / OK-attemptN  = 装好且能 import
#   FAILED-venv / FAILED      = 失败（看日志）
LOG="${FMR_INSTALL_LOG:-/tmp/vllm_install.log}"
VENV="${FMR_VENV:-/mnt/shared-storage-user/ai4good1-share/majiachen/.venvs/fmr-vllm}"
PY="$VENV/bin/python"; PIP="$VENV/bin/pip"; MARK="$VENV/.install_state"

log() { echo "$(date '+%F %T') $*" >> "$LOG"; }

log "=== 开始（venv=$VENV）==="
mkdir -p "$(dirname "$VENV")" 2>/dev/null || true

# 1) venv（共享卷上 virtiofs 较慢，可能要几分钟）
if [ ! -x "$PY" ]; then
  log "创建 venv…"
  python3 -m venv --system-site-packages "$VENV" >> "$LOG" 2>&1 || { log "venv 创建失败"; echo "FAILED-venv" > "$MARK" 2>/dev/null; exit 1; }
  log "venv 就绪"
fi
"$PIP" install -q -U pip >> "$LOG" 2>&1 || true

# 2) 幂等：已能 import 就直接收工
if "$PY" -c "import vllm" 2>/dev/null; then
  log "vllm 已存在：$("$PY" -c 'import vllm;print(vllm.__version__)' 2>/dev/null)"
  echo "OK-already" > "$MARK"; exit 0
fi

# 3) 带重试安装（网络抖动/镜像慢不至于前功尽弃）
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-/tmp/pip-cache}"; mkdir -p "$PIP_CACHE_DIR"
for i in 1 2 3; do
  log "--- 第 $i 次尝试 ---"
  if "$PIP" install --retries 10 --timeout 60 --no-input vllm >> "$LOG" 2>&1; then
    if "$PY" -c "import vllm; print('vllm', vllm.__version__)" >> "$LOG" 2>&1; then
      log "安装成功（第 $i 次）"; echo "OK-attempt$i" > "$MARK"; exit 0
    fi
    log "装完但 import 失败，继续重试"
  else
    log "第 $i 次失败，30s 后重试"
  fi
  sleep 30
done

log "=== 三次均失败 ==="
echo "FAILED" > "$MARK"
exit 1
