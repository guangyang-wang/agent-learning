# 后端镜像：Python + FastAPI/uvicorn（前端由 nginx 容器单独提供）
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# 依赖层放前面：requirements.txt 没变时复用缓存，只重装源码
COPY requirements.txt .
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple
RUN pip install --no-cache-dir -r requirements.txt -i "$PIP_INDEX_URL"

COPY src ./src

# 运行期数据目录（compose 会用宿主机目录覆盖，保证重启不丢）
RUN mkdir -p memory data/uploads chroma_db

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["uvicorn", "agent.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
