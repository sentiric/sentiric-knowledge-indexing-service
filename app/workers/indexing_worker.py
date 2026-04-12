# app/workers/indexing_worker.py
import asyncio
import structlog
import asyncpg
import uuid
from datetime import datetime, timezone

# [ARCH-COMPLIANCE FIX]: 'Optional' importunun olduğundan emin olun
from typing import List, Optional

from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.core.models import DataSource
from app.core.chunking import split_text_into_chunks
from app.core import metrics
from app.ingesters import ingester_factory

logger = structlog.get_logger()

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
        # [ARCH-COMPLIANCE] Initialization Trace Context
        structlog.contextvars.bind_contextvars(
            trace_id=str(uuid.uuid4()), span_id=str(uuid.uuid4())
        )
        try:
            logger.info(
                f"Loading embedding model: {settings.QDRANT_DB_EMBEDDING_MODEL_NAME}",
                event_name="MODEL_LOADING_START",
            )

            self.model = await asyncio.to_thread(
                SentenceTransformer,
                settings.QDRANT_DB_EMBEDDING_MODEL_NAME,
                cache_folder="/app/model-cache",
            )

            await self._wait_for_service("Qdrant", self._check_qdrant)
            await self._wait_for_service("PostgreSQL", self._check_postgres)

            logger.info(
                "All dependencies (Vector DB, Postgres, Model) are ready.",
                event_name="DEPENDENCIES_READY",
            )
            self.app_state.is_ready = True
        except Exception as e:
            logger.fatal(
                f"Critical infrastructure failed to start. {e}",
                event_name="INFRASTRUCTURE_FAILURE",
                exc_info=True,
            )
            self.app_state.is_ready = False
            raise
        finally:
            structlog.contextvars.clear_contextvars()

    async def _wait_for_service(
        self, service_name: str, check_function, retries=10, delay=5
    ):
        for i in range(retries):
            try:
                await check_function()
                logger.info(
                    f"{service_name} connection established.",
                    event_name="SERVICE_CONNECTED",
                    service=service_name,
                )
                return
            except Exception as e:
                logger.warn(
                    f"{service_name} connection attempt {i + 1}/{retries} failed.",
                    event_name="SERVICE_CONNECT_RETRY",
                    service=service_name,
                    error=str(e),
                )
                if i == retries - 1:
                    raise e
                await asyncio.sleep(delay)

    async def _check_qdrant(self):
        def _sync_check():
            client = QdrantClient(
                url=settings.QDRANT_HTTP_URL,
                api_key=settings.QDRANT_API_KEY,
                timeout=10,
            )
            client.get_collections()
            return client

        self.qdrant_client = await asyncio.wait_for(
            asyncio.to_thread(_sync_check), timeout=15
        )

    async def _check_postgres(self):
        conn = None
        try:
            conn = await asyncio.wait_for(
                asyncpg.connect(dsn=settings.POSTGRES_URL), timeout=10
            )
            await conn.execute("SELECT 1")
        finally:
            if conn:
                await conn.close()

    # HATA VEREN 1. YER: Parametre 'str = None' yerine 'Optional[str] = None' yapıldı.
    async def _get_datasources_to_index(
        self, tenant_id: Optional[str] = None
    ) -> list[DataSource]:
        datasources = []
        conn = None
        try:
            conn = await asyncio.wait_for(
                asyncpg.connect(dsn=settings.POSTGRES_URL), timeout=15
            )
            query = "SELECT id, tenant_id, source_type, source_uri, last_indexed_at FROM datasources WHERE is_active = TRUE"
            args = []

            if tenant_id and tenant_id != "all":
                query += " AND tenant_id = $1"
                args.append(tenant_id)

            query += " ORDER BY last_indexed_at NULLS FIRST, updated_at ASC LIMIT 50"

            records = await conn.fetch(query, *args)
            datasources = [DataSource(**record) for record in records]

            if datasources:
                logger.info(
                    f"{len(datasources)} datasources queued for indexing.",
                    event_name="DATASOURCES_QUEUED",
                    count=len(datasources),
                )
        # [ARCH-COMPLIANCE FIX] Kullanılmayan 'e' değişkeni loga parametre olarak aktarıldı. (Satır 143 civarı)
        except Exception as e:
            logger.error(
                "Failed to fetch datasources.",
                event_name="DB_FETCH_ERROR",
                error=str(e),
                exc_info=True,
            )
        finally:
            if conn:
                await conn.close()
        return datasources

    async def _update_datasource_status(
        self, source_id: int, status: str, update_time: bool = False
    ):
        conn = None
        try:
            conn = await asyncio.wait_for(
                asyncpg.connect(dsn=settings.POSTGRES_URL), timeout=10
            )
            if update_time:
                await conn.execute(
                    "UPDATE datasources SET last_indexed_at = $1, last_status = $2 WHERE id = $3",
                    datetime.now(timezone.utc),
                    status,
                    source_id,
                )
            else:
                await conn.execute(
                    "UPDATE datasources SET last_status = $1 WHERE id = $2",
                    status,
                    source_id,
                )
        except Exception as e:
            logger.error(
                f"Failed to update datasource status for {source_id}",
                event_name="DB_UPDATE_ERROR",
                source_id=source_id,
                error=str(e),
            )
        finally:
            if conn:
                await conn.close()

    async def _compute_embeddings(self, texts: List[str]) -> List[List[float]]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.model.encode(
                texts, batch_size=EMBEDDING_BATCH_SIZE, show_progress_bar=False
            ).tolist(),
        )

    # HATA VEREN 2. YER: Parametre 'str = None' yerine 'Optional[str] = None' yapıldı.
    @metrics.INDEXING_CYCLE_DURATION_SECONDS.time()
    async def run_indexing_cycle(self, tenant_id: Optional[str] = None):
        # [ARCH-COMPLIANCE] Ensure Cycle Context
        cycle_trace_id = str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(
            trace_id=cycle_trace_id, span_id=str(uuid.uuid4())
        )

        if self._is_running:
            logger.warn(
                "Indexing cycle already running. Skip.", event_name="INDEXING_SKIPPED"
            )
            structlog.contextvars.clear_contextvars()
            return

        self._is_running = True
        logger.info(
            f"Indexing cycle started for tenant: {tenant_id or 'all'}",
            event_name="INDEXING_CYCLE_START",
        )

        try:
            datasources = await self._get_datasources_to_index(tenant_id)
            if not datasources:
                logger.info(
                    "No active datasources found.", event_name="INDEXING_CYCLE_EMPTY"
                )
                return

            for source in datasources:
                # [ARCH-COMPLIANCE] Strict span isolation per document source
                structlog.contextvars.bind_contextvars(
                    span_id=str(uuid.uuid4()), tenant_id=source.tenant_id
                )
                await self._process_single_datasource(source)

            metrics.LAST_INDEXING_TIMESTAMP.set_to_current_time()
            logger.info(
                "Indexing cycle completed successfully.",
                event_name="INDEXING_CYCLE_END",
            )

        except Exception as e:
            logger.error(
                f"Fatal error during indexing cycle: {e}",
                event_name="INDEXING_CYCLE_ERROR",
                exc_info=True,
            )
        finally:
            structlog.contextvars.clear_contextvars()
            self._is_running = False

    async def _process_single_datasource(self, source: DataSource):
        log = logger.bind(source_uri=source.source_uri)

        try:
            await self._update_datasource_status(source.id, "in_progress")
            log.info("Processing datasource.", event_name="DATASOURCE_PROCESS_START")

            ingester = ingester_factory(source)
            documents = await ingester.load(source)
            metrics.DOCUMENTS_LOADED_TOTAL.labels(
                tenant_id=source.tenant_id, source_type=source.source_type
            ).inc(len(documents))

            if not documents:
                log.warn("Datasource returned empty.", event_name="DATASOURCE_EMPTY")
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
                log.warn("No chunks created.", event_name="CHUNK_GENERATION_FAILED")
                await self._update_datasource_status(source.id, "no_chunks")
                return

            log.info(
                f"Vectorizing {len(all_chunks)} chunks...",
                event_name="VECTORIZATION_START",
                chunk_count=len(all_chunks),
            )
            vectors = await self._compute_embeddings(all_chunks)

            collection_name = (
                f"{settings.QDRANT_DB_COLLECTION_PREFIX}{source.tenant_id}"
            )
            await self.ensure_collection_exists(collection_name)

            def _sync_delete():
                self.qdrant_client.delete(
                    collection_name=collection_name,
                    points_selector=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="source_uri",
                                match=models.MatchValue(value=source.source_uri),
                            )
                        ]
                    ),
                )

            await asyncio.wait_for(asyncio.to_thread(_sync_delete), timeout=15)

            points = [
                models.PointStruct(
                    id=str(uuid.uuid4()), vector=v, payload=all_payloads[i]
                )
                for i, v in enumerate(vectors)
            ]

            total_upserted = 0
            for i in range(0, len(points), UPSERT_BATCH_SIZE):
                batch = points[i : i + UPSERT_BATCH_SIZE]

                def _sync_upsert(b):
                    self.qdrant_client.upsert(
                        collection_name=collection_name, points=b, wait=True
                    )

                await asyncio.wait_for(
                    asyncio.to_thread(_sync_upsert, batch), timeout=30
                )
                total_upserted += len(batch)

            metrics.VECTORS_UPSERTED_TOTAL.labels(
                tenant_id=source.tenant_id, collection=collection_name
            ).inc(total_upserted)

            await self._update_datasource_status(source.id, "success", update_time=True)
            metrics.DATASOURCES_PROCESSED_TOTAL.labels(
                tenant_id=source.tenant_id,
                source_type=source.source_type,
                status="success",
            ).inc()
            log.info(
                f"Indexing successful for {total_upserted} vectors.",
                event_name="DATASOURCE_PROCESS_END",
                vectors_count=total_upserted,
            )

        except asyncio.TimeoutError:
            log.error(
                "Network timeout during indexing operation.",
                event_name="DATASOURCE_PROCESS_TIMEOUT",
            )
            await self._update_datasource_status(source.id, "failed")
        except Exception as e:
            log.error(
                f"Error processing datasource: {e}",
                event_name="DATASOURCE_PROCESS_ERROR",
                exc_info=True,
            )
            await self._update_datasource_status(source.id, "failed")
            metrics.DATASOURCES_PROCESSED_TOTAL.labels(
                tenant_id=source.tenant_id,
                source_type=source.source_type,
                status="failed",
            ).inc()

    async def ensure_collection_exists(self, collection_name: str):
        def _sync_ensure():
            try:
                self.qdrant_client.get_collection(collection_name=collection_name)
            except Exception:
                logger.info(
                    f"Creating vector collection: {collection_name}",
                    event_name="QDRANT_COLLECTION_CREATE",
                )
                self.qdrant_client.recreate_collection(
                    collection_name=collection_name,
                    vectors_config=models.VectorParams(
                        size=self.model.get_sentence_embedding_dimension(),
                        distance=models.Distance.COSINE,
                    ),
                )
                self.qdrant_client.create_payload_index(
                    collection_name=collection_name,
                    field_name="source_uri",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
                self.qdrant_client.create_payload_index(
                    collection_name=collection_name,
                    field_name="source_type",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )

        await asyncio.wait_for(asyncio.to_thread(_sync_ensure), timeout=15)

    async def start_worker_loop(self):
        try:
            await self.initialize()
        except Exception:
            logger.error(
                "Worker failed to initialize, entering retry loop.",
                event_name="WORKER_INIT_FAILED",
            )

        await self.run_indexing_cycle()

        while True:
            try:
                await asyncio.wait_for(
                    self.trigger_event.wait(),
                    timeout=settings.KNOWLEDGE_INDEXING_INTERVAL_SECONDS,
                )
                self.trigger_event.clear()
                await self.run_indexing_cycle()
            except asyncio.TimeoutError:
                await self.run_indexing_cycle()
            except Exception as e:
                structlog.contextvars.bind_contextvars(
                    trace_id=str(uuid.uuid4()), span_id=str(uuid.uuid4())
                )
                logger.error(
                    f"Error in worker main loop: {e}",
                    event_name="WORKER_LOOP_ERROR",
                    exc_info=True,
                )
                structlog.contextvars.clear_contextvars()
                await asyncio.sleep(60)
