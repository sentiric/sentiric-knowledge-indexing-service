# sentiric-knowledge-indexing-service/app/main.py
import asyncio
from app.core.logging import setup_logging
from app.core.config import settings
from app.workers.indexing_worker import start_worker_loop
from app.core.health import start_health_server # <-- YENİ IMPORT
import structlog

logger = structlog.get_logger(__name__)

def main():
    setup_logging()
    
    logger.info("Knowledge Indexing Service başlatılıyor...", 
                version=settings.SERVICE_VERSION, 
                env=settings.ENV)
    
    # Ana worker döngüsüne başlamadan ÖNCE health check sunucusunu başlat
    start_health_server()
    
    # Worker modunu başlat
    logger.info("Worker modu başlatılıyor, sürekli indeksleme döngüsü bekleniyor...")
    asyncio.run(start_worker_loop())

if __name__ == "__main__":
    main()