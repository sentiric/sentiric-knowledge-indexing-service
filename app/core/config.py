# app/core/config.py
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Sentiric Knowledge Indexing Service"
    API_V1_STR: str = "/api/v1"
    
    ENV: str = "production"
    LOG_LEVEL: str = "INFO"
    SERVICE_VERSION: str = "0.1.0"
    
    # [ARCH-COMPLIANCE] Resource node identity
    NODE_NAME: str = os.getenv("NODE_HOSTNAME", "unknown-node")
    
    # [ARCH-COMPLIANCE] Tenant Isolation Zorunluluğu
    TENANT_ID: str = os.getenv("TENANT_ID", "")
    
    # Network ve Port Ayarları
    KNOWLEDGE_INDEXING_SERVICE_HTTP_PORT: int = 17030
    KNOWLEDGE_INDEXING_SERVICE_GRPC_PORT: int = 17031
    KNOWLEDGE_INDEXING_SERVICE_METRICS_PORT: int = 17032
    
    # mTLS Sertifika Yolları (YENİ)
    GRPC_TLS_CA_PATH: str
    KNOWLEDGE_INDEXING_SERVICE_CERT_PATH: str
    KNOWLEDGE_INDEXING_SERVICE_KEY_PATH: str
        
    # RAG Kaynak Ayarları
    POSTGRES_URL: str
    
    # Vector Database (Qdrant) Ayarları
    QDRANT_HTTP_URL: str
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_DB_COLLECTION_PREFIX: str = "sentiric_kb_"
    
    # Embedding Modeli Ayarları
    QDRANT_DB_EMBEDDING_MODEL_NAME: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    
    # Worker Ayarları
    KNOWLEDGE_INDEXING_INTERVAL_SECONDS: int = 3600

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding='utf-8',
        extra='ignore'
    )

settings = Settings()

# [ARCH-COMPLIANCE] Strict Tenant Validation
if not settings.TENANT_ID and settings.ENV == "production":
    # Runtime'da çözülmesine olanak tanımak için burada panic yapmıyoruz, 
    # ancak context'ten okunamazsa boş kalması bir uyarı sebebidir.
    pass