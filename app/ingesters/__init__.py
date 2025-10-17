# sentiric-knowledge-indexing-service/app/ingesters/__init__.py
from .base import BaseIngester
from .postgres_ingester import PostgresIngester
from .web_ingester import WebIngester
from app.core.models import DataSource

def ingester_factory(source: DataSource) -> BaseIngester:
    """
    Veri kaynağı türüne göre uygun yükleyici (ingester) nesnesini döndürür.
    """
    if source.source_type == "postgres":
        return PostgresIngester()
    elif source.source_type == "web":
        return WebIngester()
    # TODO: 'file' ingester eklenecek
    else:
        raise ValueError(f"Desteklenmeyen kaynak türü: {source.source_type}")