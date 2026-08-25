#!/usr/bin/env bash
# 杀掉占用8790端口的进程(精确制导), 再清pid文件
PID=$(ss -tlnp 2>/dev/null | grep ':8790' | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2)
if [ -n "$PID" ]; then kill "$PID" 2>/dev/null && echo "已停止(pid=$PID)"; else echo "端口空闲"; fi
rm -f "$DIR_PID"; DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; rm -f "$DIR/.pid"
