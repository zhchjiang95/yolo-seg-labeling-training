#!/bin/bash
# ==============================================================================
# YOLO26s-seg 智能分割训练平台 - 服务启动脚本 (智能自愈与防重复启动)
# ==============================================================================

# 1. 确保进入脚本所在目录（避免由于外部路径执行导致相对路径失效）
cd "$(dirname "$0")" || exit 1

PORT=9523
PID_FILE="service.pid"
LOG_DIR="logs"
LOG_FILE="$LOG_DIR/systemout.log"

# 创建日志目录
mkdir -p "$LOG_DIR"

# 2. 智能探测 Python 解释器（优先使用配置的专用虚拟环境，不存在则自动回退）
PYTHON_BIN="/app/tools/yolo-env/bin/python"
if [ ! -x "$PYTHON_BIN" ] && [ ! -f "$PYTHON_BIN" ]; then
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN=$(command -v python3)
    elif command -v python >/dev/null 2>&1; then
        PYTHON_BIN=$(command -v python)
    else
        echo "[ERROR] 未找到可用的 Python 解释器，请先安装 Python 或配置 /app/tools/yolo-env/！"
        exit 1
    fi
fi

# 3. 辅助函数：跨平台/工具链获取占用指定端口的所有 PID (兼容 lsof / fuser / ss / netstat)
get_pids_on_port() {
    local target_port=$1
    local pids=""

    # 方式一：lsof (最精确)
    if command -v lsof >/dev/null 2>&1; then
        pids=$(lsof -ti :"$target_port" 2>/dev/null)
    fi

    # 方式二：fuser
    if [ -z "$pids" ] && command -v fuser >/dev/null 2>&1; then
        pids=$(fuser "$target_port"/tcp 2>/dev/null | tr -s ' ' '\n')
    fi

    # 方式三：ss
    if [ -z "$pids" ] && command -v ss >/dev/null 2>&1; then
        pids=$(ss -lntp 2>/dev/null | grep ":$target_port " | grep -o 'pid=[0-9]*' | cut -d= -f2)
    fi

    # 方式四：netstat
    if [ -z "$pids" ] && command -v netstat >/dev/null 2>&1; then
        pids=$(netstat -lntp 2>/dev/null | grep ":$target_port " | awk '{print $7}' | cut -d/ -f1 | grep -E '^[0-9]+$')
    fi

    # 整理去重输出 PID 列表
    echo "$pids" | tr ' ' '\n' | grep -E '^[0-9]+$' | sort -u
}

# 4. 辅助函数：判断服务是否真正、健康地在运行
is_service_running() {
    # 必须满足两个条件：
    # 条件A：PID 文件存在，且里面记录的 PID 进程活跃
    if [ -f "$PID_FILE" ]; then
        local recorded_pid
        recorded_pid=$(cat "$PID_FILE" 2>/dev/null | tr -d ' ')
        if [ -n "$recorded_pid" ] && kill -0 "$recorded_pid" 2>/dev/null; then
            # 条件B：端口 9523 正在被正常监听
            local port_pids
            port_pids=$(get_pids_on_port "$PORT")
            if [ -n "$port_pids" ]; then
                return 0
            fi
        fi
    fi
    return 1
}

# ==============================================================================
# 5. 主流程判断
# ==============================================================================

# 场景 A：如果服务确实正在正常运行中，则不进行任何重复启动操作
if is_service_running; then
    CURRENT_PID=$(cat "$PID_FILE" 2>/dev/null | tr -d ' ')
    echo "=================================================================="
    echo " [INFO] 服务当前已在正常运行中，无需重复启动！"
    echo " 进程 PID : $CURRENT_PID"
    echo " 监听端口 : $PORT"
    echo " 访问地址 : http://0.0.0.0:$PORT/"
    echo " 实时日志 : tail -f $LOG_FILE"
    echo " 如需重启请执行: ./restart.sh 或 ./stop.sh 后再执行 ./start.sh"
    echo "=================================================================="
    exit 0
fi

# 场景 B：服务未正常运行，执行强制清理异常残留并重新启动
echo "[INIT] 服务未运行或处于异常状态，正在准备启动..."

# 强制清理 1：若 pid 文件中记录的历史进程仍在，先尝试优雅终止
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE" 2>/dev/null | tr -d ' ')
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[CLEAN] 终止历史记录的残留进程 PID=$OLD_PID..."
        kill -15 "$OLD_PID" 2>/dev/null
    fi
    rm -f "$PID_FILE"
fi

# 强制清理 2：扫描 9523 端口，若存在任何孤儿或残留进程，强制 kill 释放端口
PORT_PIDS=$(get_pids_on_port "$PORT")
if [ -n "$PORT_PIDS" ]; then
    CLEAN_PIDS_STR=$(echo "$PORT_PIDS" | tr '\n' ' ')
    echo "[WARN] 检测到端口 $PORT 被残留进程占用 (PID: $CLEAN_PIDS_STR)，正在强制清理释放..."
    for p in $PORT_PIDS; do
        kill -15 "$p" 2>/dev/null
    done
    sleep 1.5

    # 二次检查，若未退出则强制 kill -9
    PORT_PIDS=$(get_pids_on_port "$PORT")
    if [ -n "$PORT_PIDS" ]; then
        echo "[WARN] 进程仍未退出，执行强制杀除 (kill -9)..."
        for p in $PORT_PIDS; do
            kill -9 "$p" 2>/dev/null
        done
        sleep 1
    fi
fi

# 确认端口是否成功释放
PORT_PIDS=$(get_pids_on_port "$PORT")
if [ -n "$PORT_PIDS" ]; then
    echo "=================================================================="
    echo " [ERROR] 无法释放端口 $PORT，仍被进程 PID: $(echo "$PORT_PIDS" | tr '\n' ' ') 占用！"
    echo " 请检查是否有权限（可能需要 sudo）或手动执行: kill -9 $(echo "$PORT_PIDS" | tr '\n' ' ')"
    echo "=================================================================="
    exit 1
fi

# 6. 正式拉起服务
echo "[START] 正在启动 FastAPI 后端服务..."
echo "[START] Python 解释器: $PYTHON_BIN"

nohup "$PYTHON_BIN" main.py > "$LOG_FILE" 2>&1 &
NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"

# 7. 启动状态自检验证（防止秒退或假死）
echo "[CHECK] 正在检验服务存活及端口监听状态..."
IS_SUCCESS=0
for i in $(seq 1 10); do
    sleep 0.5
    # 检查新进程是否夭折
    if ! kill -0 "$NEW_PID" 2>/dev/null; then
        echo "=================================================================="
        echo " [ERROR] 服务启动失败！进程已提前退出 (PID: $NEW_PID)。"
        echo " 最近 25 行错误日志 ($LOG_FILE):"
        echo "------------------------------------------------------------------"
        tail -n 25 "$LOG_FILE"
        echo "=================================================================="
        rm -f "$PID_FILE"
        exit 1
    fi

    # 检查端口是否已绑定成功
    PORT_PIDS=$(get_pids_on_port "$PORT")
    if [ -n "$PORT_PIDS" ]; then
        IS_SUCCESS=1
        break
    fi
done

echo "=================================================================="
if [ "$IS_SUCCESS" -eq 1 ]; then
    echo " [SUCCESS] YOLO26s-seg 训练控制台服务启动成功！"
    echo " 进程 PID : $NEW_PID"
    echo " 绑定端口 : $PORT"
    echo " 控制台地址: http://0.0.0.0:$PORT/"
    echo " 实时日志 : tail -f $LOG_FILE"
else
    echo " [WARN] 进程存活 (PID: $NEW_PID)，端口正在绑定中（可能正在加载基础环境/模型）。"
    echo " 请通过以下命令跟踪启动进度: tail -f $LOG_FILE"
fi
echo "=================================================================="
exit 0