#!/bin/bash
# 启动 AULA 离线驱动 (前端已本地化, CDN 按需缓存)
# 用法: ./start.sh [--offline] [--port 8080]
cd "$(dirname "$0")"
python3 server.py "$@"
