FROM python:3.14-slim AS base

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY config ./config
COPY api.py main.py ./

RUN uv sync --no-dev --group api \
    && useradd -m instarag \
    && mkdir -p /data \
    && chown -R instarag:instarag /app /data

USER instarag

ENV INSTARAG_DATA_DIR=/data
ENV INSTARAG_CONFIG_DIR=/data/config
ENV INSTARAG_HOST=0.0.0.0
ENV INSTARAG_PORT=8000

VOLUME ["/data"]
EXPOSE 8000

CMD ["uv", "run", "src/api/main.py"]
