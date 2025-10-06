# sentiric-knowledge-indexing-service/app/main.py
import asyncio
from app.core.logging import setup_logging
from app.core.config import settings
from app.workers.indexing_worker import start_worker_loop
import structlog
import os

logger = structlog.get_logger(__name__)

# Bu servis genellikle bir arkaplan işleyicisi (worker) olarak çalışır.
# API arayüzü, sadece TriggerReindex RPC'si için gereklidir.

def main():
    setup_logging()
    
    logger.info("Knowledge Indexing Service başlatılıyor (Worker Modu)", 
                version=settings.SERVICE_VERSION, 
                env=settings.ENV)
    
    # TriggerReindex RPC'sini dinlemek için Uvicorn/FastAPI veya sadece 
    # sürekli çalışan bir worker loop'u başlatılabilir.
    
    if os.environ.get("RUN_MODE") == "API":
        # API Modu (RPC dinleme)
        logger.info("API modu başlatılıyor...")
        # from fastapi_app import app 
        # uvicorn.run(app, host="0.0.0.0", port=settings.HTTP_PORT)
    else:
        # Worker Modu (Sürekli Veri İşleme)
        logger.info("Worker modu başlatılıyor, sürekli indeksleme döngüsü bekleniyor...")
        asyncio.run(start_worker_loop())

if __name__ == "__main__':
    main()