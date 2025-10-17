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
        """Bağımlılıkları (model, db istemcisi) başlatır ve hazır olmalarını bekler."""
        try:
            # --- MODEL YÜKLEME ---
            # Bu adım ağa bağımlı olabilir (eğer model volume'de yoksa).
            # cache_folder, modelin Docker volume'ünden okunmasını sağlar.
            logger.info("Embedding modeli yükleniyor...", model=settings.QDRANT_DB_EMBEDDING_MODEL_NAME)
            self.model = SentenceTransformer(
                settings.QDRANT_DB_EMBEDDING_MODEL_NAME, 
                cache_folder="/app/model-cache" # HF_HOME ile tutarlı
            )
            
            # --- BAĞLANTI KONTROLLERİ (YENİDEN DENEME MEKANİZMASI İLE) ---
            await self._wait_for_service("Qdrant", self._check_qdrant)
            await self._wait_for_service("PostgreSQL", self._check_postgres)
            
            logger.info("Tüm bağımlılıklar (Vector DB, PostgreSQL, Model) hazır.")
            self.app_state.is_ready = True # Sadece her şey hazırsa servisi sağlıklı olarak işaretle
        except Exception as e:
            logger.critical("Kritik altyapı başlatılamadı, worker durduruluyor.", error=str(e), exc_info=True)
            self.app_state.is_ready = False
            # Bu hata, uygulamanın çökmesine ve Docker'ın yeniden başlatmasına neden olur ki bu istenen bir davranıştır.
            raise

    async def _wait_for_service(self, service_name: str, check_function, retries=5, delay=5):
        """Bir servisin hazır olmasını bekleyen yardımcı fonksiyon."""
        for i in range(retries):
            try:
                await check_function()
                logger.info(f"{service_name} bağlantısı başarılı.")
                return
            except Exception as e:
                logger.warning(
                    f"{service_name} için bağlantı denemesi {i+1}/{retries} başarısız. {delay} saniye sonra tekrar denenecek.",
                    error=str(e)
                )
                if i == retries - 1: # Son denemede de başarısız olursa
                    logger.error(f"{service_name} servisine {retries} denemeden sonra bağlanılamadı.")
                    raise e
                await asyncio.sleep(delay)

    async def _check_qdrant(self):
        """Qdrant bağlantısını ve hazır olup olmadığını kontrol eder."""
        # Bağlantı kurarken kısa bir timeout belirle
        client = QdrantClient(url=settings.QDRANT_HTTP_URL, api_key=settings.QDRANT_API_KEY, timeout=10)
        client.get_collections() # Bu komut, sunucuya başarılı bir istek atıp atamadığımızı kontrol eder.
        self.qdrant_client = client # Bağlantı başarılıysa, nesneyi sakla

    async def _check_postgres(self):
        """PostgreSQL bağlantısını kontrol eder."""
        conn = None
        try:
            conn = await asyncpg.connect(dsn=settings.POSTGRES_URL, timeout=10)
            # Basit bir sorgu çalıştırarak bağlantının canlı olduğunu teyit et
            await conn.execute("SELECT 1")
        finally:
            if conn:
                await conn.close()

    async def _get_datasources_to_index(self, tenant_id: str = None) -> list[DataSource]:
        """PostgreSQL'den indekslenecek veri kaynaklarını çeker."""
        datasources = []
        conn = None
        try:
            conn = await asyncpg.connect(dsn=settings.POSTGRES_URL)
            if tenant_id:
                records = await conn.fetch("SELECT id, tenant_id, source_type, source_uri FROM datasources WHERE tenant_id = $1 AND is_active = TRUE", tenant_id)
            else:
                records = await conn.fetch("SELECT id, tenant_id, source_type, source_uri FROM datasources WHERE is_active = TRUE")
            
            datasources = [DataSource(**record) for record in records]
            if datasources:
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
            logger.debug("Veri kaynağının zaman damgası güncellendi.", source_id=source_id)
        except Exception as e:
            logger.error("Zaman damgası güncellenirken hata oluştu.", source_id=source_id, error=str(e))
        finally:
            if conn:
                await conn.close()

    async def run_indexing_cycle(self, tenant_id: str = None):
        """Tek bir tam indeksleme döngüsünü çalıştırır."""
        logger.info("İndeksleme döngüsü başlatıldı.", trigger_tenant=tenant_id or "all")
        
        datasources = await self._get_datasources_to_index(tenant_id)
        if not datasources:
            logger.info("İşlenecek aktif veri kaynağı bulunamadı.")
            return
        
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
                        ids=None,
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
        try:
            await self.initialize()
        except Exception:
             # initialize() içinde zaten kritik hata loglandı. Burada tekrar loglamaya gerek yok.
             # Uygulamanın çökmesine izin vererek Docker'ın restart politikasının devreye girmesini sağlıyoruz.
            return
        
        # Periyodik döngüye girmeden önce bir başlangıç indekslemesi yap.
        await self.run_indexing_cycle()

        while True:
            try:
                # `wait_for` ile hem periyodik çalışmayı (timeout) hem de manuel tetiklemeyi (event) yönetiyoruz.
                await asyncio.wait_for(
                    self.trigger_event.wait(),
                    timeout=settings.KNOWLEDGE_INDEXING_INTERVAL_SECONDS
                )
                self.trigger_event.clear()
                logger.info("Manuel tetikleme ile indeksleme döngüsü başlatılıyor.")
                await self.run_indexing_cycle()
            except asyncio.TimeoutError:
                # Zaman aşımı ile tetiklendi (periyodik çalışma)
                logger.info("Periyodik zamanlama ile indeksleme döngüsü başlatılıyor.")
                await self.run_indexing_cycle()
            except Exception as e:
                logger.error("Worker ana döngüsünde beklenmedik bir hata oluştu. Döngü devam edecek.", error=str(e), exc_info=True)
                # Kritik olmayan hatalarda bir süre bekleyip devam et
                await asyncio.sleep(60)