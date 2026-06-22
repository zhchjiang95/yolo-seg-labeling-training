#!/bin/bash

PID=$(cat service.pid)

# 杀整个进程组
kill -- -$(ps -o pgid= $PID | tr -d ' ')

rm -f service.pid

echo "停止成功"