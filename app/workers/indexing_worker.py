# sentiric-knowledge-indexing-service/app/workers/indexing_worker.py
import asyncio
import structlog
from app.core.config import settings
from app.ingesters.postgres_ingester import fetch_data_from_postgres
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from sentence_transformers import SentenceTransformer

logger = structlog.get_logger(__name__)

async def start_worker_loop():
    logger.info("Indeksleme Worker'ı başlatılıyor.")
    
    model = None
    qdrant_client = None

    try:
        model = SentenceTransformer(settings.QDRANT_DB_EMBEDDING_MODEL_NAME)
        qdrant_client = QdrantClient(url=settings.QDRANT_HTTP_URL, api_key=settings.QDRANT_API_KEY)
        logger.info("Vector DB ve Embedding Model'i hazır.")
    except Exception as e:
        logger.critical("Vektörleştirme altyapısı başlatılamadı, worker durduruluyor.", error=str(e), exc_info=True)
        return

    while True:
        try:
            logger.info("Periyodik indeksleme döngüsü başlatıldı.")
            
            # Gerçekte, get_tenants() gibi bir fonksiyonla tüm tenant'ları almalıyız.
            # Şimdilik mock tenant ile devam edelim.
            tenants_to_index = ["mock_tenant"] # veya get_tenants()
            
            for tenant_id in tenants_to_index:
                logger.info("Tenant için indeksleme başlıyor.", tenant_id=tenant_id)
                # Placeholder: Veritabanından veri çek
                postgres_data = await fetch_data_from_postgres(tenant_id, "health_services")
                
                if not postgres_data:
                    logger.warn("İndekslenecek veri bulunamadı.", tenant_id=tenant_id)
                    continue

                logger.info(f"{len(postgres_data)} doküman vektörleştiriliyor.", tenant_id=tenant_id)
                
                collection_name = f"{settings.QDRANT_DB_COLLECTION_PREFIX}{tenant_id}"
                
                # Koleksiyonu oluştur veya doğrula
                qdrant_client.recreate_collection(
                    collection_name=collection_name, 
                    vectors_config=VectorParams(size=model.get_sentence_embedding_dimension(), distance=Distance.COSINE)
                )
                
                # Vektörleştirme ve Qdrant'a yazma
                vectors = model.encode([item.content for item in postgres_data])
                qdrant_client.upload_collection(
                    collection_name=collection_name,
                    vectors=vectors,
                    payload=[{"text": item.content, "source": item.source} for item in postgres_data],
                    ids=None, # Qdrant otomatik ID atasın
                    batch_size=256
                )
                
                logger.info("İndeksleme işlemi tamamlandı.", collection=collection_name)

        except Exception as e:
            # --- KRİTİK DEĞİŞİKLİK ---
            # Döngü içinde herhangi bir hata olursa, logla ve döngüye devam et.
            # Bu, servisin çökmesini engeller.
            logger.error("Indeksleme döngüsünde bir hata oluştu, bir sonraki döngü bekleniyor.", error=str(e), exc_info=True)
            # --- DEĞİŞİKLİK SONU ---

        logger.info(f"{settings.KNOWLEDGE_INDEXING_INTERVAL_SECONDS} saniye sonraki döngü bekleniyor.")
        await asyncio.sleep(settings.INDEXING_INTERVAL_SECONDS)