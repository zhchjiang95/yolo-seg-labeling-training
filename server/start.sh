#!/bin/bash

PID_FILE=service.pid

nohup /app/tools/yolo-env/bin/python main.py \
    > logs/systemout.log 2>&1 &

PID=$!

echo $PID > $PID_FILE

echo "启动成功 PID=$PID"