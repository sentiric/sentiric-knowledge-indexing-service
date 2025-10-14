# sentiric-knowledge-indexing-service/app/workers/indexing_worker.py
import asyncio
import structlog
from app.core.config import settings
from app.ingesters.postgres_ingester import fetch_data_from_postgres
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from sentence_transformers import SentenceTransformer
from app.core.health import health_state # <-- YENİ IMPORT

logger = structlog.get_logger(__name__)

async def start_worker_loop():
    logger.info("Indeksleme Worker'ı başlatılıyor.")
    
    model = None
    qdrant_client = None

    try:
        model = SentenceTransformer(settings.QDRANT_DB_EMBEDDING_MODEL_NAME)
        health_state.set_model_ready(True) # <-- DURUM GÜNCELLEMESİ
        
        qdrant_client = QdrantClient(url=settings.QDRANT_HTTP_URL, api_key=settings.QDRANT_API_KEY)
        # Qdrant'a basit bir ping atarak bağlantıyı doğrulayabiliriz.
        qdrant_client.get_collections() 
        health_state.set_qdrant_ready(True) # <-- DURUM GÜNCELLEMESİ
        
        logger.info("Vector DB ve Embedding Model'i hazır.")
    except Exception as e:
        logger.critical("Vektörleştirme altyapısı başlatılamadı, worker durduruluyor.", error=str(e), exc_info=True)
        # Başlatma başarısız olursa sağlık durumunu false yap ve çık
        health_state.set_model_ready(False)
        health_state.set_qdrant_ready(False)
        return

    while True:
        try:
            health_state.set_loop_running(True) # <-- DURUM GÜNCELLEMESİ
            logger.info("Periyodik indeksleme döngüsü başlatıldı.")
            
            # ... (mevcut döngü kodunuzun geri kalanı aynı kalır) ...
            
            tenants_to_index = ["mock_tenant"]
            for tenant_id in tenants_to_index:
                # ... (mevcut kod) ...
                pass
            
            logger.info("İndeksleme işlemi tamamlandı.")

        except Exception as e:
            logger.error("Indeksleme döngüsünde bir hata oluştu, bir sonraki döngü bekleniyor.", error=str(e), exc_info=True)

        logger.info(f"{settings.KNOWLEDGE_INDEXING_INTERVAL_SECONDS} saniye sonraki döngü bekleniyor.")
        await asyncio.sleep(settings.KNOWLEDGE_INDEXING_INTERVAL_SECONDS)