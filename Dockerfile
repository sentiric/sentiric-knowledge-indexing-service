### 📄 File: knowledge-indexing-service/Dockerfile (YENİ STANDART)

ARG PYTHON_VERSION=3.11
ARG BASE_IMAGE_TAG=${PYTHON_VERSION}-slim-bullseye
ARG TORCH_INDEX_URL="--extra-index-url https://download.pytorch.org/whl/cpu"

# ==================================
#      Aşama 1: Builder
# ==================================
FROM python:${BASE_IMAGE_TAG} AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev git curl && \
    rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt ${TORCH_INDEX_URL}

# ==================================
#      Aşama 2: Final Image
# ==================================
FROM python:${BASE_IMAGE_TAG}
WORKDIR /app
ARG GIT_COMMIT="unknown"
ARG BUILD_DATE="unknown"
ARG SERVICE_VERSION="0.0.0"
ENV GIT_COMMIT=${GIT_COMMIT} BUILD_DATE=${BUILD_DATE} SERVICE_VERSION=${SERVICE_VERSION} PYTHONUNBUFFERED=1 PATH="/opt/venv/bin:$PATH" \
    HF_HOME="/app/model-cache"

RUN apt-get update && apt-get install -y --no-install-recommends netcat-openbsd curl ca-certificates libpq5 libgomp1 && rm -rf /var/lib/apt/lists/*
RUN addgroup --system --gid 1001 appgroup && adduser --system --no-create-home --uid 1001 --ingroup appgroup appuser
COPY --from=builder --chown=appuser:appgroup /opt/venv /opt/venv
COPY --chown=appuser:appgroup app ./app

RUN mkdir -p /app/model-cache && \
    chown -R appuser:appgroup /app/model-cache

USER appuser
EXPOSE 17030 17031 17032
CMD ["python", "-m", "app.main"]