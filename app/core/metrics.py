# app/core/metrics.py
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
    REGISTRY,
)
import structlog
from app.core.config import settings

logger = structlog.get_logger(__name__)

# --- Metrik Tanımları ---

SERVICE_INFO = Info(
    'service_info', 
    'Knowledge Indexing Service static information'
)

INDEXING_CYCLE_DURATION_SECONDS = Histogram(
    'indexing_cycle_duration_seconds',
    'Duration of a single indexing cycle in seconds.'
)

DATASOURCES_PROCESSED_TOTAL = Counter(
    'datasources_processed_total',
    'Total number of datasources processed.',
    ['tenant_id', 'source_type', 'status'] # status: success, failed
)

DOCUMENTS_LOADED_TOTAL = Counter(
    'documents_loaded_total',
    'Total number of documents loaded from datasources.',
    ['tenant_id', 'source_type']
)

VECTORS_UPSERTED_TOTAL = Counter(
    'vectors_upserted_total',
    'Total number of vectors upserted to the vector database.',
    ['tenant_id', 'collection']
)

LAST_INDEXING_TIMESTAMP = Gauge(
    'last_indexing_timestamp_seconds',
    'Timestamp of the last successful indexing cycle completion.'
)

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; version=0.0.4')
            self.end_headers()
            self.wfile.write(generate_latest(REGISTRY))
        else:
            self.send_response(404)
            self.end_headers()

async def start_metrics_server():
    port = settings.KNOWLEDGE_INDEXING_SERVICE_METRICS_PORT
    server = HTTPServer(('', port), MetricsHandler)
    logger.info("Metrik sunucusu başlatılıyor...", address=f"http://0.0.0.0:{port}/metrics")
    
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, server.serve_forever)