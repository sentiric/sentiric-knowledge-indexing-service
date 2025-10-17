# app/main.py
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import grpc
import structlog
from fastapi import FastAPI, Response, status, Body

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.models import ReindexRequest
from app.core import metrics
from app.workers.indexing_worker import IndexingManager

# Kontratlardan gRPC stubs'larını import et
from sentiric.knowledge.v1 import indexing_pb2
from sentiric.knowledge.v1 import indexing_pb2_grpc

logger = structlog.get_logger(__name__)

class AppState:
    def __init__(self):
        self.is_ready = False
        self.indexing_manager: IndexingManager | None = None
        self.grpc_server: grpc.aio.Server | None = None

app_state = AppState()

# --- gRPC Servisi Implementasyonu ---
class KnowledgeIndexingServicer(indexing_pb2_grpc.KnowledgeIndexingServiceServicer):
    async def TriggerReindex(
        self, request: indexing_pb2.TriggerReindexRequest, context: grpc.aio.ServicerContext
    ) -> indexing_pb2.TriggerReindexResponse:
        if not app_state.is_ready or not app_state.indexing_manager:
            await context.abort(grpc.StatusCode.UNAVAILABLE, "Worker is not ready.")
        
        tenant_id = request.tenant_id if request.tenant_id else "all"
        logger.info("gRPC üzerinden yeniden indeksleme tetiklendi.", requested_tenant=tenant_id)
        
        # Worker'a anında çalışması için sinyal gönder
        app_state.indexing_manager.trigger_event.set()
        
        # Gerçek job_id (eğer asenkron task yönetimi olsaydı) buraya gelirdi
        return indexing_pb2.TriggerReindexResponse(success=True, job_id="triggered")

async def serve_grpc():
    """gRPC sunucusunu başlatır."""
    server = grpc.aio.server()
    indexing_pb2_grpc.add_KnowledgeIndexingServiceServicer_to_server(KnowledgeIndexingServicer(), server)
    
    # --- mTLS GÜVENLİK GÜNCELLEMESİ ---
    try:
        private_key = Path(settings.KNOWLEDGE_INDEXING_SERVICE_KEY_PATH).read_bytes()
        certificate_chain = Path(settings.KNOWLEDGE_INDEXING_SERVICE_CERT_PATH).read_bytes()
        ca_cert = Path(settings.GRPC_TLS_CA_PATH).read_bytes()

        server_credentials = grpc.ssl_server_credentials(
            private_key_certificate_chain_pairs=[(private_key, certificate_chain)],
            root_certificates=ca_cert,
            require_client_auth=True
        )
        listen_addr = f'[::]:{settings.KNOWLEDGE_INDEXING_SERVICE_GRPC_PORT}'
        server.add_secure_port(listen_addr, server_credentials)
        logger.info("Güvenli (mTLS) gRPC sunucusu başlatılıyor...", address=listen_addr)
    except FileNotFoundError:
        logger.warning("Sertifika dosyaları bulunamadı, güvensiz gRPC portu kullanılıyor.")
        listen_addr = f'[::]:{settings.KNOWLEDGE_INDEXING_SERVICE_GRPC_PORT}'
        server.add_insecure_port(listen_addr)
    # --- GÜNCELLEME SONU ---
    
    app_state.grpc_server = server
    await server.start()
    await server.wait_for_termination()

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    metrics.SERVICE_INFO.info({'version': settings.SERVICE_VERSION})
    logger.info("Knowledge Indexing Service başlatılıyor...", version=settings.SERVICE_VERSION, env=settings.ENV)
    
    app_state.indexing_manager = IndexingManager(app_state)
    asyncio.create_task(app_state.indexing_manager.start_worker_loop())
    
    yield
    
    logger.info("Knowledge Indexing Service kapatılıyor.")
    if app_state.grpc_server:
        await app_state.grpc_server.stop(grace=1)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="RAG indeksleme motoru (Yazma bacağı).",
    version=settings.SERVICE_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

@app.get("/health", status_code=status.HTTP_200_OK, tags=["Monitoring"])
async def health_check():
    if app_state.is_ready:
        return {"status": "healthy", "dependencies": ["qdrant", "postgres", "embedding_model"]}
    else:
        return Response(content='{"status": "initializing"}', status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

@app.post("/reindex", status_code=status.HTTP_202_ACCEPTED, tags=["Actions"])
async def trigger_reindex(request: ReindexRequest = Body(None)):
    if not app_state.is_ready or not app_state.indexing_manager:
        return Response(content='{"detail": "Worker is not ready."}', status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    tenant_id = request.tenant_id if request else "all"
    logger.info("HTTP üzerinden yeniden indeksleme tetiklendi.", requested_tenant=tenant_id)
    
    app_state.indexing_manager.trigger_event.set()
    
    return {"message": f"Re-indexing for tenant '{tenant_id}' triggered."}