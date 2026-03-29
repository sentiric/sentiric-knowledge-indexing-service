# app/runner.py
import asyncio
import uvicorn
import structlog
from app.main import app, serve_grpc
from app.core.config import settings
from app.core.metrics import start_metrics_server
from app.core.logging import setup_logging

async def main():
    # Loglama sistemini ilk adımda kur
    setup_logging()
    logger = structlog.get_logger(__name__)
    logger.info("Starting all servers...", event="SYSTEM_INIT")
    
    # [ARCH-COMPLIANCE] log_config=None verilerek uvicorn'un kendi formatını 
    # basması engellenir, her şey bizim structlog handler'ımızdan akar.
    uvicorn_config = uvicorn.Config(
        app, 
        host="0.0.0.0", 
        port=settings.KNOWLEDGE_INDEXING_SERVICE_HTTP_PORT,
        log_config=None, # KRİTİK: Varsayılan loglamayı devre dışı bırak
        access_log=False # Access logları noise yaratmaması için kapalı (İstenirse açılabilir)
    )
    uvicorn_server = uvicorn.Server(uvicorn_config)
    
    await asyncio.gather(
        uvicorn_server.serve(),
        serve_grpc(),
        start_metrics_server()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass