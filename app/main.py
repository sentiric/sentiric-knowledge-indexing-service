# sentiric-knowledge-indexing-service/app/main.py
import asyncio
from contextlib import asynccontextmanager
import structlog
from fastapi import FastAPI, Response, status, Body

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.models import ReindexRequest
from app.workers.indexing_worker import IndexingManager

logger = structlog.get_logger(__name__)

class AppState:
    def __init__(self):
        self.is_ready = False
        self.indexing_manager: IndexingManager | None = None

app_state = AppState()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Başlangıç ---
    setup_logging()
    logger.info(
        "Knowledge Indexing Service başlatılıyor...",
        version=settings.SERVICE_VERSION,
        env=settings.ENV
    )
    
    app_state.indexing_manager = IndexingManager(app_state)
    asyncio.create_task(app_state.indexing_manager.start_worker_loop())
    
    yield
    
    # --- Kapanış ---
    logger.info("Knowledge Indexing Service kapatılıyor.")

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
    """
    Worker ve bağımlılıkların durumunu kontrol eder.
    """
    if app_state.is_ready:
        return {
            "status": "healthy",
            "dependencies": ["qdrant", "embedding_model"]
        }
    else:
        return Response(
            content='{"status": "initializing", "detail": "Service is not yet ready."}',
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            media_type="application/json"
        )

@app.post("/reindex", status_code=status.HTTP_202_ACCEPTED, tags=["Actions"])
async def trigger_reindex(request: ReindexRequest = Body(None)):
    """
    İndeksleme sürecini manuel olarak tetikler.
    Boş gövde gönderilirse tüm tenant'lar, tenant_id belirtilirse sadece o tenant
    için indeksleme başlatılır (Mevcut implementasyonda tümünü tetikler).
    """
    if not app_state.is_ready or not app_state.indexing_manager:
        return Response(
            content='{"status": "service_unavailable", "detail": "Worker is not running or not ready."}',
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            media_type="application/json"
        )
    
    tenant_id = request.tenant_id if request else "all"
    logger.info("Manuel yeniden indeksleme tetiklendi.", requested_tenant=tenant_id)
    
    # Worker'a anında çalışması için sinyal gönder
    app_state.indexing_manager.trigger_event.set()
    
    return {"message": f"Re-indexing process for tenant '{tenant_id}' triggered in the background."}