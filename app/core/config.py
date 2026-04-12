# app/core/config.py
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "Sentiric Knowledge Indexing Service"
    API_V1_STR: str = "/api/v1"

    ENV: str = "production"
    LOG_LEVEL: str = "INFO"
    SERVICE_VERSION: str = (
        "0.4.6"  # [ARCH-COMPLIANCE] Versiyon pyproject.toml dan alınmalı!!!
    )

    NODE_NAME: str = os.getenv("NODE_HOSTNAME", "unknown-node")
    TENANT_ID: str = os.getenv("TENANT_ID", "")

    KNOWLEDGE_INDEXING_SERVICE_HTTP_PORT: int = 17030
    KNOWLEDGE_INDEXING_SERVICE_GRPC_PORT: int = 17031
    KNOWLEDGE_INDEXING_SERVICE_METRICS_PORT: int = 17032

    GRPC_TLS_CA_PATH: str
    KNOWLEDGE_INDEXING_SERVICE_CERT_PATH: str
    KNOWLEDGE_INDEXING_SERVICE_KEY_PATH: str

    POSTGRES_URL: str

    QDRANT_HTTP_URL: str
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_DB_COLLECTION_PREFIX: str = "sentiric_kb_"

    QDRANT_DB_EMBEDDING_MODEL_NAME: str = (
        "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    )

    KNOWLEDGE_INDEXING_INTERVAL_SECONDS: int = 3600

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()

if not settings.TENANT_ID and settings.ENV == "production":
    pass
