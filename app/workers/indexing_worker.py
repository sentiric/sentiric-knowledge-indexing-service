# sentiric-knowledge-indexing-service/app/workers/indexing_worker.py
import asyncio
import structlog
import asyncpg
from datetime import datetime, timezone
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.core.models import DataSource
from app.core.chunking import split_text_into_chunks
from app.ingesters import ingester_factory

logger = structlog.get_logger(__name__)

class IndexingManager:
    """
    İndeksleme sürecinin tüm adımlarını yöneten sınıf.
    """
    def __init__(self, app_state):
        self.app_state = app_state
        self.model = None
        self.qdrant_client = None
        self.trigger_event = asyncio.Event()

    async def initialize(self):
        """Bağımlılıkları (model, db istemcisi) başlatır."""
        try:
            logger.info("Embedding modeli yükleniyor...", model=settings.QDRANT_DB_EMBEDDING_MODEL_NAME)
            self.model = SentenceTransformer(settings.QDRANT_DB_EMBEDDING_MODEL_NAME)
            
            logger.info("Qdrant istemcisi başlatılıyor...", url=settings.QDRANT_HTTP_URL)
            self.qdrant_client = QdrantClient(url=settings.QDRANT_HTTP_URL, api_key=settings.QDRANT_API_KEY)
            self.qdrant_client.get_collections()
            
            logger.info("Vector DB ve Embedding Modeli hazır.")
            self.app_state.is_ready = True
        except Exception as e:
            logger.critical("Vektörleştirme altyapısı başlatılamadı, worker durduruluyor.", error=str(e), exc_info=True)
            self.app_state.is_ready = False
            raise

    async def _get_datasources_to_index(self, tenant_id: str = None) -> list[DataSource]:
        """PostgreSQL'den indekslenecek veri kaynaklarını çeker."""
        datasources = []
        conn = None
        try:
            conn = await asyncpg.connect(dsn=settings.POSTGRES_URL)
            if tenant_id:
                records = await conn.fetch("SELECT id, tenant_id, source_type, source_uri FROM datasources WHERE tenant_id = $1", tenant_id)
            else:
                records = await conn.fetch("SELECT id, tenant_id, source_type, source_uri FROM datasources WHERE is_active = TRUE")
            
            datasources = [DataSource(**record) for record in records]
            logger.info(f"{len(datasources)} adet veri kaynağı işlenmek üzere bulundu.")
        except Exception as e:
            logger.error("Veri kaynakları çekilirken hata oluştu.", error=str(e), exc_info=True)
        finally:
            if conn:
                await conn.close()
        return datasources
    
    async def _update_datasource_timestamp(self, source_id: int):
        """İndeksleme sonrası zaman damgasını günceller."""
        conn = None
        try:
            conn = await asyncpg.connect(dsn=settings.POSTGRES_URL)
            await conn.execute(
                "UPDATE datasources SET last_indexed_at = $1 WHERE id = $2",
                datetime.now(timezone.utc),
                source_id
            )
            logger.info("Veri kaynağının zaman damgası güncellendi.", source_id=source_id)
        except Exception as e:
            logger.error("Zaman damgası güncellenirken hata oluştu.", source_id=source_id, error=str(e))
        finally:
            if conn:
                await conn.close()

    async def run_indexing_cycle(self, tenant_id: str = None):
        """Tek bir tam indeksleme döngüsünü çalıştırır."""
        logger.info("İndeksleme döngüsü başlatıldı.", trigger_tenant=tenant_id or "all")
        
        datasources = await self._get_datasources_to_index(tenant_id)
        
        for source in datasources:
            log = logger.bind(tenant_id=source.tenant_id, source_uri=source.source_uri, source_type=source.source_type)
            try:
                log.info("Veri kaynağı işleniyor...")
                ingester = ingester_factory(source)
                documents = await ingester.load(source)

                if not documents:
                    log.warning("İşlenecek doküman bulunamadı, sonraki kaynağa geçiliyor.")
                    continue

                all_chunks = []
                all_metadatas = []
                for doc in documents:
                    chunks = split_text_into_chunks(doc.page_content)
                    all_chunks.extend(chunks)
                    all_metadatas.extend([doc.metadata] * len(chunks))

                if not all_chunks:
                    log.warning("Metin parçaları (chunks) oluşturulamadı.")
                    continue

                log.info(f"{len(all_chunks)} adet metin parçası vektöre dönüştürülüyor...")
                vectors = self.model.encode(all_chunks, show_progress_bar=False).tolist()

                collection_name = f"{settings.QDRANT_DB_COLLECTION_PREFIX}{source.tenant_id}"
                await self.ensure_collection_exists(collection_name)

                log.info(f"{len(vectors)} vektör Qdrant koleksiyonuna yazılıyor.", collection=collection_name)
                self.qdrant_client.upsert(
                    collection_name=collection_name,
                    points=models.Batch(
                        ids=None, # Qdrant otomatik ID atayacak
                        vectors=vectors,
                        payloads=all_metadatas
                    ),
                    wait=True
                )
                
                await self._update_datasource_timestamp(source.id)
                log.info("Veri kaynağı başarıyla indekslendi.")

            except Exception as e:
                log.error("Veri kaynağı işlenirken bir hata oluştu.", error=str(e), exc_info=True)

        logger.info("İndeksleme döngüsü tamamlandı.")

    async def ensure_collection_exists(self, collection_name: str):
        """Qdrant'ta koleksiyonun var olduğundan emin olur, yoksa oluşturur."""
        try:
            self.qdrant_client.get_collection(collection_name=collection_name)
        except Exception:
            logger.info(f"Koleksiyon bulunamadı, yeni koleksiyon oluşturuluyor: {collection_name}")
            self.qdrant_client.recreate_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=self.model.get_sentence_embedding_dimension(),
                    distance=models.Distance.COSINE
                )
            )

    async def start_worker_loop(self):
        """Worker'ın ana döngüsü. Periyodik olarak ve olayla tetiklenir."""
        await self.initialize()
        if not self.app_state.is_ready:
            return

        while True:
            try:
                await asyncio.wait_for(
                    asyncio.shield(self.trigger_event.wait()),
                    timeout=settings.KNOWLEDGE_INDEXING_INTERVAL_SECONDS
                )
                self.trigger_event.clear()
                # Olay ile tetiklendi, belirli bir tenant olabilir, ancak şimdilik tümünü çalıştırıyoruz.
                await self.run_indexing_cycle()
            except asyncio.TimeoutError:
                # Zaman aşımı ile tetiklendi (periyodik çalışma)
                await self.run_indexing_cycle()
            except Exception as e:
                logger.error("Worker ana döngüsünde kritik hata.", error=str(e), exc_info=True)
                # Kritik hatada bir süre bekleyip devam etmeyi dene
                await asyncio.sleep(60)