# app/core/logging.py
import logging
import sys
import structlog
from app.core.config import settings

_log_setup_done = False

def suts_v4_processor(logger, log_method, event_dict):
    """
    [ARCH-COMPLIANCE] structlog ve standart logları SUTS v4.0 JSON şemasına çevirir.
    """
    ctx = structlog.contextvars.get_contextvars()
    
    # Trace ve Span ID'lerini al
    trace_id = event_dict.pop("trace_id", ctx.get("trace_id"))
    span_id = event_dict.pop("span_id", ctx.get("span_id"))
    
    # SUTS v4.0'da 'event' zorunlu ve makine okunabilir olmalı. 
    # Eğer event yoksa message içeriğini SNAKE_CASE yapmaya çalışırız.
    raw_event = event_dict.pop("event", "LOG_EVENT")
    
    # Standart loglardan gelen 'msg' veya structlog'un 'event' (message) alanı
    message = event_dict.pop("message", event_dict.pop("msg", raw_event))
    
    # Makine okunabilir Event ID (SNAKE_CASE)
    # Eğer event açıkça verilmemişse, generic bir etiket kullanılır.
    event_id = raw_event if raw_event != message else "APPLICATION_LOG"

    suts_log = {
        "schema_v": "1.0.0",
        "ts": event_dict.pop("timestamp", None),
        "severity": log_method.upper() if log_method.upper() != "EXCEPTION" else "ERROR",
        "tenant_id": settings.TENANT_ID,
        "resource": {
            "service.name": "knowledge-indexing-service",
            "service.version": settings.SERVICE_VERSION,
            "service.env": settings.ENV,
            "host.name": settings.NODE_NAME
        },
        "trace_id": trace_id,
        "span_id": span_id,
        "event": event_id.upper().replace(" ", "_"),
        "message": message,
        "attributes": event_dict # Geriye kalan her şey attributes altına
    }
    return suts_log

def setup_logging():
    global _log_setup_done
    if _log_setup_done: return

    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # 1. STANDART LOGGING HANDLER'LARI TEMİZLE
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Standart output için handler
    handler = logging.StreamHandler(sys.stdout)
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # 2. STRUCTLOG İŞLEMCİLERİ
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", key="timestamp", utc=True),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.ENV.lower() == "development":
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        processors.append(suts_v4_processor)
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 3. UVICORN VE DİĞER KÜTÜPHANELERİ STRUCTLOG'A YÖNLENDİR
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        adv_logger = logging.getLogger(logger_name)
        adv_logger.handlers = []
        adv_logger.propagate = True

    _log_setup_done = True
    logger = structlog.get_logger("sentiric")
    logger.info("SUTS v4.0 Logging Engine Active", event="LOGGING_ENGINE_READY")