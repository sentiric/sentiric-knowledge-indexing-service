# app/runner.py
import asyncio
import uvicorn
import structlog
import logging
from app.main import app
try:
    from app.main import serve_grpc # Indexing Service
    from app.core.metrics import start_metrics_server
    is_indexing = True
except ImportError:
    is_indexing = False # Query Service

from app.core.config import settings

logger = structlog.get_logger()

async def main():
    logger.info("Starting background services...", event_name="SYSTEM_INIT")
    
    # [ARCH-COMPLIANCE] Uvicorn log config must be entirely overridden to prevent RAW leaks
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["handlers"] = {} # Disable default handlers
    
    uvicorn_config = uvicorn.Config(
        app, 
        host="0.0.0.0", 
        port=settings.KNOWLEDGE_INDEXING_SERVICE_HTTP_PORT if is_indexing else settings.KNOWLEDGE_QUERY_SERVICE_HTTP_PORT,
        log_config=log_config, 
        access_log=False 
    )
    uvicorn_server = uvicorn.Server(uvicorn_config)
    
    if is_indexing:
        await asyncio.gather(
            uvicorn_server.serve(),
            serve_grpc(),
            start_metrics_server()
        )
    else:
        await uvicorn_server.serve()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Bu aşamada structlog contexti bitmiş olabilir, taze ID atıyoruz.
        import uuid
        structlog.contextvars.bind_contextvars(trace_id=str(uuid.uuid4()), span_id=str(uuid.uuid4()))
        logger.info("Servers shutting down gracefully.", event_name="SYSTEM_SHUTDOWN")