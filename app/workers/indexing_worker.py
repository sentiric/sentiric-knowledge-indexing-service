# app/workers/indexing_worker.py
# [ARCH-COMPLIANCE] Olay döngüleri için span_id eklendi ve tüm loglara event etiketi zorunlu kılındı.
import asyncio
import structlog
import asyncpg
import uuid
from datetime import datetime, timezone
from typing import List

from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.core.models import DataSource
from app.core.chunking import split_text_into_chunks
from app.core import metrics
from app.ingesters import ingester_factory

logger = structlog.get_logger(__name__)

EMBEDDING_BATCH_SIZE = 32
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
            logger.info("Embedding modeli yükleniyor...", event="MODEL_LOADING", model=settings.QDRANT_DB_EMBEDDING_MODEL_NAME)
            self.model = SentenceTransformer(settings.QDRANT_DB_EMBEDDING_MODEL_NAME, cache_folder="/app/model-cache")
            
            await self._wait_for_service("Qdrant", self._check_qdrant)
            await self._wait_for_service("PostgreSQL", self._check_postgres)
            
            logger.info("Tüm bağımlılıklar (Vector DB, PostgreSQL, Model) hazır.", event="DEPENDENCIES_READY")
            self.app_state.is_ready = True
        except Exception as e:
            logger.critical("Kritik altyapı başlatılamadı, worker durduruluyor.", event="CRITICAL_INFRA_FAIL", error=str(e), exc_info=True)
            self.app_state.is_ready = False
            raise

    async def _wait_for_service(self, service_name: str, check_function, retries=10, delay=5):
        for i in range(retries):
            try:
                await check_function()
                logger.info(f"{service_name} bağlantısı başarılı.", event="SERVICE_CONNECTED", target_service=service_name)
                return
            except Exception as e:
                logger.warning(f"{service_name} bağlantı denemesi {i+1}/{retries} başarısız.", event="SERVICE_CONNECT_RETRY", target_service=service_name, error=str(e))
                if i == retries - 1:
                    raise e
                await asyncio.sleep(delay)

    async def _check_qdrant(self):
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
            
            query += " ORDER BY last_indexed_at NULLS FIRST, updated_at ASC LIMIT 50"
            
            records = await conn.fetch(query, *args)
            datasources = [DataSource(**record) for record in records]
            
            if datasources:
                logger.info(f"{len(datasources)} adet veri kaynağı işlenmek üzere kuyruğa alındı.", event="DATASOURCES_QUEUED", count=len(datasources))
        except Exception as e:
            logger.error("Veri kaynakları çekilirken hata oluştu.", event="DB_FETCH_ERROR", error=str(e), exc_info=True)
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
            logger.error("Veri kaynağı durumu güncellenirken hata.", event="DB_UPDATE_ERROR", source_id=source_id, error=str(e))
        finally:
            if conn:
                await conn.close()

    async def _compute_embeddings(self, texts: List[str]) -> List[List[float]]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, 
            lambda: self.model.encode(texts, batch_size=EMBEDDING_BATCH_SIZE, show_progress_bar=False).tolist()
        )

    @metrics.INDEXING_CYCLE_DURATION_SECONDS.time()
    async def run_indexing_cycle(self, tenant_id: str = None):
        ctx = structlog.contextvars.get_contextvars()
        if "trace_id" not in ctx:
            structlog.contextvars.bind_contextvars(trace_id=str(uuid.uuid4()))
        # [ARCH-COMPLIANCE] Her döngü için benzersiz bir span_id ataması
        structlog.contextvars.bind_contextvars(span_id=str(uuid.uuid4()))

        if self._is_running:
            logger.warning("İndeksleme döngüsü zaten çalışıyor, yeni istek atlandı.", event="INDEXING_CYCLE_SKIPPED")
            return
        
        self._is_running = True
        logger.info("İndeksleme döngüsü başlatıldı.", event="INDEXING_CYCLE_START", trigger_tenant=tenant_id or "all")
        
        try:
            datasources = await self._get_datasources_to_index(tenant_id)
            if not datasources:
                logger.info("İşlenecek aktif veri kaynağı bulunamadı.", event="NO_DATASOURCE_FOUND")
                return
            
            for source in datasources:
                await self._process_single_datasource(source)
                
            metrics.LAST_INDEXING_TIMESTAMP.set_to_current_time()
            logger.info("İndeksleme döngüsü tamamlandı.", event="INDEXING_CYCLE_END")
            
        except Exception as e:
            logger.error("Döngü sırasında genel hata.", event="INDEXING_CYCLE_ERROR", error=str(e), exc_info=True)
        finally:
            self._is_running = False

    async def _process_single_datasource(self, source: DataSource):
        # Kaynak işlenirken context'e o kaynağa ait span_id verilir
        structlog.contextvars.bind_contextvars(span_id=str(uuid.uuid4()))
        log = logger.bind(tenant_id=source.tenant_id, source_uri=source.source_uri)
        
        try:
            await self._update_datasource_status(source.id, "in_progress")
            log.info("Veri kaynağı işleniyor...", event="DATASOURCE_PROCESSING_START")
            
            ingester = ingester_factory(source)
            documents = await ingester.load(source)
            metrics.DOCUMENTS_LOADED_TOTAL.labels(tenant_id=source.tenant_id, source_type=source.source_type).inc(len(documents))
            
            if not documents:
                log.warning("Doküman boş döndü, atlanıyor.", event="DATASOURCE_EMPTY")
                await self._update_datasource_status(source.id, "empty_or_failed")
                return

            all_chunks = []
            all_payloads = []
            
            for doc in documents:
                chunks = split_text_into_chunks(doc.page_content)
                for chunk in chunks:
                    payload = doc.metadata.copy()
                    payload["content"] = chunk 
                    all_chunks.append(chunk)
                    all_payloads.append(payload)

            if not all_chunks:
                log.warning("Chunk oluşturulamadı.", event="CHUNK_GENERATION_FAILED")
                await self._update_datasource_status(source.id, "no_chunks")
                return

            log.info(f"{len(all_chunks)} parça vektörleştiriliyor...", event="EMBEDDING_START", chunk_count=len(all_chunks))
            vectors = await self._compute_embeddings(all_chunks)

            collection_name = f"{settings.QDRANT_DB_COLLECTION_PREFIX}{source.tenant_id}"
            await self.ensure_collection_exists(collection_name)

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
            log.info("İndeksleme başarılı.", event="DATASOURCE_PROCESSING_SUCCESS", vectors_count=total_upserted)

        except Exception as e:
            log.error("Veri kaynağı işlenirken hata.", event="DATASOURCE_PROCESSING_ERROR", error=str(e))
            await self._update_datasource_status(source.id, "failed")
            metrics.DATASOURCES_PROCESSED_TOTAL.labels(tenant_id=source.tenant_id, source_type=source.source_type, status="failed").inc()

    async def ensure_collection_exists(self, collection_name: str):
        try:
            self.qdrant_client.get_collection(collection_name=collection_name)
        except Exception:
            logger.info(f"Koleksiyon oluşturuluyor: {collection_name}", event="QDRANT_COLLECTION_CREATE")
            self.qdrant_client.recreate_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=self.model.get_sentence_embedding_dimension(),
                    distance=models.Distance.COSINE
                )
            )
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
            logger.error("Worker başlatılamadı, retry döngüsüne giriyor.", event="WORKER_INIT_FAILED")
        
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
                logger.error("Worker ana döngüsünde hata.", event="WORKER_LOOP_ERROR", error=str(e), exc_info=True)
                await asyncio.sleep(60)