# --- STAGE 1: Builder ---
FROM python:3.11-slim-bullseye AS builder

# Gerekli sistem bağımlılıkları (sentence-transformers ve asyncpg için)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgomp1 \
    cmake \
    libopenblas-dev \
    git && \
    rm -rf /var/lib/apt/lists/*

# Poetry kurulumu
RUN pip install poetry

# Build argümanlarını tanımla
ARG GIT_COMMIT="unknown"
ARG BUILD_DATE="unknown"
ARG SERVICE_VERSION="0.0.0"

WORKDIR /app

# Proje dosyalarını kopyala
COPY pyproject.toml ./
COPY app ./app
COPY README.md .

# Bağımlılıkları kur
RUN poetry install --no-root --only main

# --- STAGE 2: Production ---
FROM python:3.11-slim-bullseye

WORKDIR /app

# Gerekli sistem bağımlılıkları (libpq-dev ve libgomp1 runtime için)
RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd \
    curl \
    ca-certificates \
    libpq5 \
    libgomp1 && \
    rm -rf /var/lib/apt/lists/*

# Root olmayan kullanıcı oluştur
RUN useradd -m -u 1001 appuser

# Builder'dan sanal ortam bağımlılıklarını kopyala
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /app/app ./app

# Dosya sahipliğini yeni kullanıcıya ver
RUN chown -R appuser:appuser /app

# YENİ: Build argümanlarını environment değişkenlerine ata
ARG GIT_COMMIT
ARG BUILD_DATE
ARG SERVICE_VERSION
ENV GIT_COMMIT=${GIT_COMMIT}
ENV BUILD_DATE=${BUILD_DATE}
ENV SERVICE_VERSION=${SERVICE_VERSION}

USER appuser

# Başlangıç komutu: Bu servis arka plan işlerini yapar, API portu isteğe bağlıdır. 
# Genellikle API/gRPC portu 12040 (Knowledge Query) tarafından kullanılır. Bu servis 
# çoğunlukla arkaplan worker olarak çalışacaktır, bu yüzden `main.py` dosyasını kullanıyoruz.
CMD ["python", "-m", "app.main"]