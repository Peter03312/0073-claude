#!/usr/bin/env bash
# 一次性 verify 服务：后端测试 → 前端构建 → 端到端冒烟，全部通过后退出 0
set -euo pipefail

echo "══ 1/3 后端单元与接口测试 ══"
cd /work/backend
python -m pytest tests -q

echo ""
echo "══ 2/3 前端类型检查与构建 ══"
cd /work/frontend
npm run build

echo ""
echo "══ 3/3 端到端冒烟（api + web） ══"
python /work/verify/smoke.py

echo ""
echo "✔ VERIFY OK：测试、构建、冒烟全部通过"
