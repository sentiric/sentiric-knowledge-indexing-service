# sentiric-knowledge-indexing-service/app/core/health.py
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

class HealthState:
    """Uygulamanın sağlık durumunu tutan thread-safe bir sınıf."""
    def __init__(self):
        self._lock = threading.Lock()
        self.model_ready = False
        self.qdrant_ready = False
        self.loop_running = False

    def set_model_ready(self, status: bool):
        with self._lock:
            self.model_ready = status

    def set_qdrant_ready(self, status: bool):
        with self._lock:
            self.qdrant_ready = status
            
    def set_loop_running(self, status: bool):
        with self._lock:
            self.loop_running = status

    def is_healthy(self) -> bool:
        with self._lock:
            # Sağlıklı sayılmak için tüm kritik bileşenlerin hazır olması gerekir.
            return self.model_ready and self.qdrant_ready and self.loop_running

# Global sağlık durumu nesnesi
health_state = HealthState()

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Gelen /health isteklerini işleyen handler."""
    def do_GET(self):
        if self.path == '/health':
            if health_state.is_healthy():
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status": "ok"}')
            else:
                self.send_response(503) # Service Unavailable
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status": "unhealthy"}')
        else:
            self.send_response(404)
            self.end_headers()


    # YENİ METOT: Bu metot, access loglarını konsola yazmayı engeller.
    def log_message(self, format, *args):
        return

def start_health_serve(port: int = 17032):
    """HTTP health check sunucusunu ayrı bir thread'de başlatır."""
    server = HTTPServer(('', port), HealthCheckHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True  # Ana program sonlandığında bu thread'in de sonlanmasını sağlar
    thread.start()
    print(f"🩺 Health check sunucusu port {port} üzerinde başlatıldı.")