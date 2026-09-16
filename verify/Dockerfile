# 一次性 verify 服务：python（跑后端测试与冒烟）+ node（构建前端）
FROM python:3.12-slim
COPY --from=node:20-bookworm-slim /usr/local/ /usr/local/

ENV PYTHONUNBUFFERED=1
WORKDIR /work

# 后端依赖（含测试依赖）
COPY backend/requirements.txt backend/requirements-dev.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements-dev.txt

# 前端依赖（先装依赖以利用镜像层缓存）
COPY frontend/package.json frontend/package-lock.json* ./frontend/
RUN cd frontend && npm install --no-audit --no-fund

# 源码与示例
COPY backend ./backend
COPY frontend ./frontend
COPY examples ./examples
COPY verify ./verify

ENV PYTHONPATH=/work/backend
CMD ["bash", "verify/run.sh"]
