# app/workers/indexing_worker.py
import asyncio
import time
import structlog
import asyncpg
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any

from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.core.models import DataSource
from app.core.chunking import split_text_into_chunks
from app.core import metrics
from app.ingesters import ingester_factory

logger = structlog.get_logger(__name__)

# Model embedding işlemi için batch size (Bellek yönetimi için kritik)
EMBEDDING_BATCH_SIZE = 32
# Qdrant upsert işlemi için batch size
UPSERT_BATCH_SIZE = 100

class IndexingManager:
    def __init__(self, app_state):
        self.app_state = app_state
        self.model = None
        self.qdrant_client = None
        self.trigger_event = asyncio.Event()
        self._is_running = False

    async def initialize(self):
        try:
            logger.info("Embedding modeli yükleniyor...", model=settings.QDRANT_DB_EMBEDDING_MODEL_NAME)
            # Modeli thread içinde yükleyerek ana döngüyü bloklamasını engellemeye çalışıyoruz ama init aşamasında bloklamak kabul edilebilir.
            self.model = SentenceTransformer(settings.QDRANT_DB_EMBEDDING_MODEL_NAME, cache_folder="/app/model-cache")
            
            await self._wait_for_service("Qdrant", self._check_qdrant)
            await self._wait_for_service("PostgreSQL", self._check_postgres)
            
            logger.info("Tüm bağımlılıklar (Vector DB, PostgreSQL, Model) hazır.")
            self.app_state.is_ready = True
        except Exception as e:
            logger.critical("Kritik altyapı başlatılamadı, worker durduruluyor.", error=str(e), exc_info=True)
            self.app_state.is_ready = False
            raise

    async def _wait_for_service(self, service_name: str, check_function, retries=10, delay=5):
        for i in range(retries):
            try:
                await check_function()
                logger.info(f"{service_name} bağlantısı başarılı.")
                return
            except Exception as e:
                logger.warning(f"{service_name} bağlantı denemesi {i+1}/{retries} başarısız.", error=str(e))
                if i == retries - 1:
                    raise e
                await asyncio.sleep(delay)

    async def _check_qdrant(self):
        # Senkron client, thread içinde çalıştırılabilir ama init için direkt çağırıyoruz
        client = QdrantClient(url=settings.QDRANT_HTTP_URL, api_key=settings.QDRANT_API_KEY, timeout=10)
        client.get_collections()
        self.qdrant_client = client

    async def _check_postgres(self):
        conn = None
        try:
            conn = await asyncpg.connect(dsn=settings.POSTGRES_URL, timeout=10)
            await conn.execute("SELECT 1")
        finally:
            if conn:
                await conn.close()

    async def _get_datasources_to_index(self, tenant_id: str = None) -> list[DataSource]:
        datasources = []
        conn = None
        try:
            conn = await asyncpg.connect(dsn=settings.POSTGRES_URL)
            query = "SELECT id, tenant_id, source_type, source_uri, last_indexed_at FROM datasources WHERE is_active = TRUE"
            args = []
            
            if tenant_id and tenant_id != "all":
                query += " AND tenant_id = $1"
                args.append(tenant_id)
            
            # Önceliklendirme: Hiç indekslenmemişler önce, sonra eskiler
            query += " ORDER BY last_indexed_at NULLS FIRST, updated_at ASC LIMIT 50"
            
            records = await conn.fetch(query, *args)
            datasources = [DataSource(**record) for record in records]
            
            if datasources:
                logger.info(f"{len(datasources)} adet veri kaynağı işlenmek üzere kuyruğa alındı.")
        except Exception as e:
            logger.error("Veri kaynakları çekilirken hata oluştu.", error=str(e), exc_info=True)
        finally:
            if conn:
                await conn.close()
        return datasources

    async def _update_datasource_status(self, source_id: int, status: str, update_time: bool = False):
        conn = None
        try:
            conn = await asyncpg.connect(dsn=settings.POSTGRES_URL)
            if update_time:
                await conn.execute(
                    "UPDATE datasources SET last_indexed_at = $1, last_status = $2 WHERE id = $3",
                    datetime.now(timezone.utc), status, source_id
                )
            else:
                await conn.execute(
                    "UPDATE datasources SET last_status = $1 WHERE id = $2",
                     status, source_id
                )
        except Exception as e:
            logger.error("Veri kaynağı durumu güncellenirken hata.", source_id=source_id, error=str(e))
        finally:
            if conn:
                await conn.close()

    # --- DÜZELTME: convert_to_numpy=True (default) kullanılarak .tolist() hatası giderildi ---
    async def _compute_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        CPU-bound olan embedding işlemini ana event loop'u bloklamadan
        ayrı bir thread'de çalıştırır.
        """
        loop = asyncio.get_running_loop()
        # Executor içinde senkron fonksiyonu çağır
        # convert_to_numpy=True varsayılan davranıştır, numpy array döner, .tolist() çalışır.
        return await loop.run_in_executor(
            None, 
            lambda: self.model.encode(texts, batch_size=EMBEDDING_BATCH_SIZE, show_progress_bar=False).tolist()
        )

    @metrics.INDEXING_CYCLE_DURATION_SECONDS.time()
    async def run_indexing_cycle(self, tenant_id: str = None):
        if self._is_running:
            logger.warning("İndeksleme döngüsü zaten çalışıyor, yeni istek atlandı.")
            return
        
        self._is_running = True
        logger.info("İndeksleme döngüsü başlatıldı.", trigger_tenant=tenant_id or "all")
        
        try:
            datasources = await self._get_datasources_to_index(tenant_id)
            if not datasources:
                logger.info("İşlenecek aktif veri kaynağı bulunamadı.")
                return
            
            for source in datasources:
                await self._process_single_datasource(source)
                
            metrics.LAST_INDEXING_TIMESTAMP.set_to_current_time()
            logger.info("İndeksleme döngüsü tamamlandı.")
            
        except Exception as e:
            logger.error("Döngü sırasında genel hata.", error=str(e), exc_info=True)
        finally:
            self._is_running = False

    async def _process_single_datasource(self, source: DataSource):
        log = logger.bind(tenant_id=source.tenant_id, source_uri=source.source_uri)
        
        try:
            await self._update_datasource_status(source.id, "in_progress")
            log.info("Veri kaynağı işleniyor...")
            
            # 1. Veriyi Çek (IO Bound)
            ingester = ingester_factory(source)
            documents = await ingester.load(source)
            metrics.DOCUMENTS_LOADED_TOTAL.labels(tenant_id=source.tenant_id, source_type=source.source_type).inc(len(documents))
            
            if not documents:
                log.warning("Doküman boş döndü, atlanıyor.")
                await self._update_datasource_status(source.id, "empty_or_failed")
                return

            # 2. Chunking (CPU Bound - hafif)
            all_chunks = []
            all_payloads = []
            
            for doc in documents:
                chunks = split_text_into_chunks(doc.page_content)
                for chunk in chunks:
                    payload = doc.metadata.copy()
                    payload["content"] = chunk # Retrieval için kritik
                    
                    all_chunks.append(chunk)
                    all_payloads.append(payload)

            if not all_chunks:
                log.warning("Chunk oluşturulamadı.")
                await self._update_datasource_status(source.id, "no_chunks")
                return

            # 3. Embedding (CPU Bound - AĞIR - Thread'e taşındı)
            log.info(f"{len(all_chunks)} parça vektörleştiriliyor...")
            vectors = await self._compute_embeddings(all_chunks)

            # 4. Koleksiyon Yönetimi (IO Bound)
            collection_name = f"{settings.QDRANT_DB_COLLECTION_PREFIX}{source.tenant_id}"
            await self.ensure_collection_exists(collection_name)

            # 5. Upsert (IO Bound - Batching ile)
            # Veriyi eski kaynaktan temizle (Overwrite stratejisi)
            # source_uri'ye göre eski vektörleri sil ki duplikasyon olmasın
            self.qdrant_client.delete(
                collection_name=collection_name,
                points_selector=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="source_uri",
                            match=models.MatchValue(value=source.source_uri)
                        )
                    ]
                )
            )

            points = []
            for i, vector in enumerate(vectors):
                points.append(models.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload=all_payloads[i]
                ))

            # Batch upsert
            total_upserted = 0
            for i in range(0, len(points), UPSERT_BATCH_SIZE):
                batch = points[i : i + UPSERT_BATCH_SIZE]
                self.qdrant_client.upsert(
                    collection_name=collection_name,
                    points=batch,
                    wait=True
                )
                total_upserted += len(batch)
            
            metrics.VECTORS_UPSERTED_TOTAL.labels(tenant_id=source.tenant_id, collection=collection_name).inc(total_upserted)
            
            await self._update_datasource_status(source.id, "success", update_time=True)
            metrics.DATASOURCES_PROCESSED_TOTAL.labels(tenant_id=source.tenant_id, source_type=source.source_type, status="success").inc()
            log.info("İndeksleme başarılı.", vectors_count=total_upserted)

        except Exception as e:
            log.error("Veri kaynağı işlenirken hata.", error=str(e))
            await self._update_datasource_status(source.id, "failed")
            metrics.DATASOURCES_PROCESSED_TOTAL.labels(tenant_id=source.tenant_id, source_type=source.source_type, status="failed").inc()

    async def ensure_collection_exists(self, collection_name: str):
        try:
            self.qdrant_client.get_collection(collection_name=collection_name)
        except Exception:
            logger.info(f"Koleksiyon oluşturuluyor: {collection_name}")
            self.qdrant_client.recreate_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=self.model.get_sentence_embedding_dimension(),
                    distance=models.Distance.COSINE
                )
            )
            # Payload Indexing (Filtreleme performansı için kritik)
            self.qdrant_client.create_payload_index(
                collection_name=collection_name,
                field_name="source_uri",
                field_schema=models.PayloadSchemaType.KEYWORD
            )
            self.qdrant_client.create_payload_index(
                collection_name=collection_name,
                field_name="source_type",
                field_schema=models.PayloadSchemaType.KEYWORD
            )

    async def start_worker_loop(self):
        try:
            await self.initialize()
        except Exception:
            logger.error("Worker başlatılamadı, retry döngüsüne giriyor.")
            # Kritik hata olsa bile container'ı öldürme, retry yap.
        
        # İlk açılışta bir tur çalıştır
        await self.run_indexing_cycle()

        while True:
            try:
                await asyncio.wait_for(
                    self.trigger_event.wait(),
                    timeout=settings.KNOWLEDGE_INDEXING_INTERVAL_SECONDS
                )
                self.trigger_event.clear()
                await self.run_indexing_cycle()
            except asyncio.TimeoutError:
                await self.run_indexing_cycle()
            except Exception as e:
                logger.error("Worker ana döngüsünde hata.", error=str(e), exc_info=True)
                await asyncio.sleep(60)