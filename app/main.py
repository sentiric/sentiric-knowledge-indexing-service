# app/main.py
import asyncio
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import grpc
import structlog
from fastapi import FastAPI, Response, status, Body, Request 

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.models import ReindexRequest
from app.core import metrics
from app.workers.indexing_worker import IndexingManager

from sentiric.knowledge.v1 import indexing_pb2
from sentiric.knowledge.v1 import indexing_pb2_grpc

logger = structlog.get_logger()

class AppState:
    def __init__(self):
        self.is_ready = False
        self.indexing_manager: IndexingManager | None = None
        self.grpc_server: grpc.aio.Server | None = None

app_state = AppState()

class KnowledgeIndexingServicer(indexing_pb2_grpc.KnowledgeIndexingServiceServicer):
    async def TriggerReindex(
        self, request: indexing_pb2.TriggerReindexRequest, context: grpc.aio.ServicerContext
    ) -> indexing_pb2.TriggerReindexResponse:
        
        metadata = dict(context.invocation_metadata())
        trace_id = metadata.get("x-trace-id", str(uuid.uuid4()))
        structlog.contextvars.bind_contextvars(trace_id=trace_id)

        if not app_state.is_ready or not app_state.indexing_manager:
            logger.error("Worker is not ready to process RPC", event_name="RPC_REJECTED")
            await context.abort(grpc.StatusCode.UNAVAILABLE, "Worker is not ready.")
        
        tenant_id = request.tenant_id if request.tenant_id else "all"
        logger.info(f"gRPC re-index triggered for tenant: {tenant_id}", event_name="RPC_REINDEX_TRIGGERED", requested_tenant=tenant_id)
        
        app_state.indexing_manager.trigger_event.set()
        
        return indexing_pb2.TriggerReindexResponse(success=True, job_id="triggered")

async def serve_grpc():
    server = grpc.aio.server()
    indexing_pb2_grpc.add_KnowledgeIndexingServiceServicer_to_server(KnowledgeIndexingServicer(), server)
    
    try:
        private_key = Path(settings.KNOWLEDGE_INDEXING_SERVICE_KEY_PATH).read_bytes()
        certificate_chain = Path(settings.KNOWLEDGE_INDEXING_SERVICE_CERT_PATH).read_bytes()
        ca_cert = Path(settings.GRPC_TLS_CA_PATH).read_bytes()
    except Exception as e:
        logger.fatal(f"Missing mTLS certificates. Unencrypted traffic risk. Error: {e}", event_name="MTLS_CONFIG_MISSING")
        sys.exit(1)

    server_credentials = grpc.ssl_server_credentials(
        private_key_certificate_chain_pairs=[(private_key, certificate_chain)],
        root_certificates=ca_cert,
        require_client_auth=True
    )
    
    listen_addr = f'[::]:{settings.KNOWLEDGE_INDEXING_SERVICE_GRPC_PORT}'
    server.add_secure_port(listen_addr, server_credentials)
    logger.info(f"Secure (mTLS) gRPC server starting on {listen_addr}", event_name="GRPC_SERVER_START")
    
    app_state.grpc_server = server
    await server.start()
    await server.wait_for_termination()

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    
    structlog.contextvars.bind_contextvars(trace_id=str(uuid.uuid4()))
    metrics.SERVICE_INFO.info({'version': settings.SERVICE_VERSION})
    logger.info(f"Knowledge Indexing Service booting up (v{settings.SERVICE_VERSION})", event_name="SYSTEM_STARTUP")
    
    app_state.indexing_manager = IndexingManager(app_state)
    asyncio.create_task(app_state.indexing_manager.start_worker_loop())
    
    yield
    
    logger.info("Knowledge Indexing Service is gracefully shutting down", event_name="SERVICE_STOPPED")
    if app_state.grpc_server:
        await app_state.grpc_server.stop(grace=5)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="RAG indeksleme motoru (Yazma bacağı).",
    version=settings.SERVICE_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    trace_id = request.headers.get("x-trace-id", str(uuid.uuid4()))
    structlog.contextvars.bind_contextvars(trace_id=trace_id)
    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id
    return response

@app.get("/health", status_code=status.HTTP_200_OK, tags=["Monitoring"])
async def health_check():
    if app_state.is_ready:
        return {"status": "healthy", "dependencies": ["qdrant", "postgres", "embedding_model"]}
    else:
        return Response(content='{"status": "initializing"}', status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

@app.post("/reindex", status_code=status.HTTP_202_ACCEPTED, tags=["Actions"])
async def trigger_reindex(request: ReindexRequest = Body(None)):
    if not app_state.is_ready or not app_state.indexing_manager:
        logger.error("Worker is not ready for HTTP reindex", event_name="HTTP_REJECTED")
        return Response(content='{"detail": "Worker is not ready."}', status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    tenant_id = request.tenant_id if request else "all"
    logger.info(f"HTTP re-indexing triggered for tenant: {tenant_id}", event_name="HTTP_REINDEX_TRIGGERED", requested_tenant=tenant_id)
    
    app_state.indexing_manager.trigger_event.set()
    
    return {"message": f"Re-indexing for tenant '{tenant_id}' triggered."}