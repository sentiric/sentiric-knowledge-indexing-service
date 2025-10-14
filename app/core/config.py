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
    POSTGRES_URL: Optional[str] = None # PostgreSQL'den veri çekmek için
    RABBITMQ_URL: Optional[str] = None # Event dinlemek için
    
    # Vector Database (Qdrant) Ayarları
    QDRANT_HTTP_URL: str
    QDRANT_GRPC_URL: Optional[str] = None
    QDRANT_API_KEY: Optional[str] = None
    
    # Qdrant'ta oluşturulacak koleksiyonların ön eki. Sonuna tenant_id eklenecek.
    QDRANT_DB_COLLECTION_PREFIX: str = "sentiric_kb_"
    
    # Metinleri vektöre çevirmek için kullanılacak model. İki servisin de aynı modeli kullanması şarttır.
    QDRANT_DB_EMBEDDING_MODEL_NAME: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    
    # Bu servise özgü ayarlar
    # Worker'ın ne sıklıkla yeniden indeksleme yapacağı (saniye cinsinden)
    KNOWLEDGE_INDEXING_INTERVAL_SECONDS: int = 3600 # Saatlik indeksleme

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding='utf-8',
        extra='ignore'
    )

settings = Settings()