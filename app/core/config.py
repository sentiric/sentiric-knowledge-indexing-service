# sentiric-knowledge-indexing-service/app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Sentiric Knowledge Indexing Service"
    API_V1_STR: str = "/api/v1"
    
    ENV: str = "production"
    LOG_LEVEL: str = "INFO"
    SERVICE_VERSION: str = "0.1.0"
    
    # RAG Kaynak Ayarları
    DATABASE_URL: Optional[str] = None # PostgreSQL'den veri çekmek için
    RABBITMQ_URL: Optional[str] = None # Event dinlemek için
    
    # Vector Database (Qdrant) Ayarları
    QDRANT_URL: str
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION_PREFIX: str = "sentiric_kb_"
    
    # Embedding Model Ayarları (Indeksleme ve Query'de aynı olmalı)
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    
    # Worker Ayarları
    INDEXING_INTERVAL_SECONDS: int = 3600 # Saatlik indeksleme

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding='utf-8',
        extra='ignore'
    )

settings = Settings()