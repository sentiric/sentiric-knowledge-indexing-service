# app/ingesters/postgres_ingester.py
import asyncpg
import structlog
from typing import List
from .base import BaseIngester
from app.core.config import settings
from app.core.models import Document, DataSource

logger = structlog.get_logger(__name__)

class PostgresIngester(BaseIngester):

    async def load(self, source: DataSource) -> List[Document]:
        if not settings.POSTGRES_URL:
            logger.error("PostgreSQL URL'si tanımlı değil. Bu yükleyici çalıştırılamaz.", event="POSTGRES_URL_MISSING")
            return []

        try:
            table_full, columns_str = source.source_uri.split('(')
            columns_str = columns_str.rstrip(')')
            columns = [c.strip() for c in columns_str.split(',')]
            content_column = columns[0]
            metadata_columns = columns[1:]
            
            query = f'SELECT {", ".join(columns)} FROM {table_full} WHERE tenant_id = $1'
            logger.info("Veritabanından veri çekiliyor...", event="POSTGRES_INGEST_START", query=query, tenant=source.tenant_id)

        except ValueError:
            logger.error("Postgres source_uri formatı geçersiz.", event="POSTGRES_URI_INVALID", uri=source.source_uri)
            return []

        conn = None
        try:
            conn = await asyncpg.connect(settings.POSTGRES_URL)
            records = await conn.fetch(query, source.tenant_id)
            
            documents = []
            for record in records:
                content = record[content_column]
                metadata = {
                    "source_uri": source.source_uri,
                    "source_type": source.source_type,
                    "tenant_id": source.tenant_id
                }
                for col in metadata_columns:
                    metadata[col] = record[col]
                
                documents.append(Document(page_content=str(content), metadata=metadata))
            
            logger.info(f"{len(documents)} adet doküman veritabanından yüklendi.", event="POSTGRES_INGEST_SUCCESS", table=table_full)
            return documents
        except Exception as e:
            logger.error("PostgreSQL'den veri çekilirken hata oluştu.", event="POSTGRES_INGEST_ERROR", error=str(e), exc_info=True)
            return []
        finally:
            if conn:
                await conn.close()