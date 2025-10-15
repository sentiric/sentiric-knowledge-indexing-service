# sentiric-knowledge-indexing-service/app/main.py
import asyncio
from contextlib import asynccontextmanager
import structlog
from fastapi import FastAPI, Response, status

from app.core.config import settings
from app.core.logging import setup_logging
from app.workers.indexing_worker import start_worker_loop

logger = structlog.get_logger(__name__)

# Worker'ın ve bağımlılıkların durumunu tutacak basit bir global nesne
class AppState:
    def __init__(self):
        self.is_ready = False

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
    
    # Uzun süren worker döngüsünü arka planda başlat, sunucunun açılışını engellemesin.
    # app_state nesnesini worker'a iletiyoruz ki durumunu güncelleyebilsin.
    asyncio.create_task(start_worker_loop(app_state))
    
    yield
    
    # --- Kapanış ---
    logger.info("Knowledge Indexing Service kapatılıyor.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="RAG indeksleme motoru (Yazma bacağı).",
    version=settings.SERVICE_VERSION,
    lifespan=lifespan,
    docs_url=None, 
    redoc_url=None
)

@app.get("/health", status_code=status.HTTP_200_OK, include_in_schema=False)
async def health_check():
    """
    Worker döngüsü ve bağımlılıkları tam olarak hazır olduğunda 200, henüz değilken 503 döner.
    Bu, Docker healthcheck'lerinin doğru çalışmasını sağlar.
    """
    if app_state.is_ready:
        return {"status": "healthy"}
    else:
        return Response(
            content='{"status": "initializing"}',
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            media_type="application/json"
        )