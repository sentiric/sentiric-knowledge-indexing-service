# app/runner.py
import asyncio
import uvicorn
import structlog
from app.main import app, serve_grpc
from app.core.config import settings
from app.core.metrics import start_metrics_server

logger = structlog.get_logger()

async def main():
    # [ARCH-COMPLIANCE] TypeError'ı çözen event_name kullanımı
    logger.info("Starting all servers...", event_name="SYSTEM_INIT")
    
    uvicorn_config = uvicorn.Config(
        app, 
        host="0.0.0.0", 
        port=settings.KNOWLEDGE_INDEXING_SERVICE_HTTP_PORT,
        log_config=None,
        access_log=False
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
        logger.info("Servers shutting down gracefully.", event_name="SYSTEM_SHUTDOWN")