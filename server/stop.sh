#!/bin/bash
# ==============================================================================
# YOLO26s-seg 智能分割训练平台 - 服务停止脚本 (干净释放与进程清理)
# ==============================================================================

# 进入脚本所在目录
cd "$(dirname "$0")" || exit 1

PORT=9523
PID_FILE="service.pid"

# 辅助函数：跨平台获取占用指定端口的所有 PID
get_pids_on_port() {
    local target_port=$1
    local pids=""

    if command -v lsof >/dev/null 2>&1; then
        pids=$(lsof -ti :"$target_port" 2>/dev/null)
    fi

    if [ -z "$pids" ] && command -v fuser >/dev/null 2>&1; then
        pids=$(fuser "$target_port"/tcp 2>/dev/null | tr -s ' ' '\n')
    fi

    if [ -z "$pids" ] && command -v ss >/dev/null 2>&1; then
        pids=$(ss -lntp 2>/dev/null | grep ":$target_port " | grep -o 'pid=[0-9]*' | cut -d= -f2)
    fi

    if [ -z "$pids" ] && command -v netstat >/dev/null 2>&1; then
        pids=$(netstat -lntp 2>/dev/null | grep ":$target_port " | awk '{print $7}' | cut -d/ -f1 | grep -E '^[0-9]+$')
    fi

    echo "$pids" | tr ' ' '\n' | grep -E '^[0-9]+$' | sort -u
}

echo "[STOP] 正在停止 YOLO26s-seg 训练控制台服务..."

KILLED_ANY=0

# 1. 如果存在 PID 文件，清理记录的主进程及进程组
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE" 2>/dev/null | tr -d ' ')
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        echo "[STOP] 正在终止主进程 PID=$PID ..."
        PGID=$(ps -o pgid= "$PID" 2>/dev/null | tr -d ' ')
        if [ -n "$PGID" ]; then
            kill -TERM -"$PGID" 2>/dev/null || kill -TERM "$PID" 2>/dev/null
        else
            kill -TERM "$PID" 2>/dev/null
        fi
        KILLED_ANY=1
    fi
    rm -f "$PID_FILE"
fi

# 2. 兜底扫描端口 9523，确保无任何孤儿或残留进程
PORT_PIDS=$(get_pids_on_port "$PORT")
if [ -n "$PORT_PIDS" ]; then
    CLEAN_PIDS_STR=$(echo "$PORT_PIDS" | tr '\n' ' ')
    echo "[STOP] 检测到端口 $PORT 仍有残留进程 (PID: $CLEAN_PIDS_STR)，正在清理..."
    for p in $PORT_PIDS; do
        kill -15 "$p" 2>/dev/null
    done
    sleep 1

    PORT_PIDS=$(get_pids_on_port "$PORT")
    if [ -n "$PORT_PIDS" ]; then
        echo "[STOP] 残留进程未响应，执行强制终止 (kill -9)..."
        for p in $PORT_PIDS; do
            kill -9 "$p" 2>/dev/null
        done
        sleep 0.5
    fi
    KILLED_ANY=1
fi

# 3. 深度扫描并强杀可能残留的 YOLO 孤儿训练子进程（彻底回收 GPU 显存）
TRAIN_PIDS=$(pgrep -f "temp_run.py" 2>/dev/null)
if [ -n "$TRAIN_PIDS" ]; then
    CLEAN_TRAIN_STR=$(echo "$TRAIN_PIDS" | tr '\n' ' ')
    echo "[STOP] 检测到孤儿训练进程正在后台占用 GPU 显存 (PID: $CLEAN_TRAIN_STR)，正在强制回收..."
    for tp in $TRAIN_PIDS; do
        kill -9 "$tp" 2>/dev/null
    done
    sleep 0.5
    echo "[SUCCESS] 已强制终止孤儿训练进程，GPU 显存已成功释放！"
    KILLED_ANY=1
fi

# 4. 输出停止结果
PORT_PIDS=$(get_pids_on_port "$PORT")
if [ -z "$PORT_PIDS" ]; then
    if [ "$KILLED_ANY" -eq 1 ]; then
        echo "[SUCCESS] 服务与训练进程已完全停止，端口 $PORT 与 GPU 资源已成功释放！"
    else
        echo "[INFO] 服务未在运行（端口 $PORT 未被占用）。"
    fi
else
    echo "[ERROR] 端口 $PORT 仍被 PID: $(echo "$PORT_PIDS" | tr '\n' ' ') 占用，请检查权限或手动处理！"
    exit 1
fi
exit 0