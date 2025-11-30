from .base import BaseIngester
from .postgres_ingester import PostgresIngester
from .web_ingester import WebIngester
from .file_ingester import FileIngester  # EKLENDİ
from app.core.models import DataSource

def ingester_factory(source: DataSource) -> BaseIngester:
    """
    Veri kaynağı türüne göre uygun yükleyici (ingester) nesnesini döndürür.
    """
    if source.source_type == "postgres":
        return PostgresIngester()
    elif source.source_type == "web":
        return WebIngester()
    elif source.source_type == "file":  # EKLENDİ
        return FileIngester()
    else:
        raise ValueError(f"Desteklenmeyen kaynak türü: {source.source_type}")