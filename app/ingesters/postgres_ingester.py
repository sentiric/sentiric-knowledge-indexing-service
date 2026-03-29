# app/ingesters/postgres_ingester.py
import asyncpg
import structlog
from typing import List
import asyncio
from .base import BaseIngester
from app.core.config import settings
from app.core.models import Document, DataSource

logger = structlog.get_logger()

class PostgresIngester(BaseIngester):
    async def load(self, source: DataSource) -> List[Document]:
        if not settings.POSTGRES_URL:
            logger.error("PostgreSQL URL is not defined.", event_name="INGEST_POSTGRES_NO_CONFIG")
            return []

        try:
            table_full, columns_str = source.source_uri.split('(')
            columns_str = columns_str.rstrip(')')
            columns = [c.strip() for c in columns_str.split(',')]
            content_column = columns[0]
            metadata_columns = columns[1:]
            
            query = f'SELECT {", ".join(columns)} FROM {table_full} WHERE tenant_id = $1'
            logger.info("Fetching data from postgres...", event_name="INGEST_POSTGRES_FETCH", query=query)

        except ValueError:
            logger.error(f"Invalid source_uri format: {source.source_uri}", event_name="INGEST_POSTGRES_INVALID_URI")
            return []

        conn = None
        try:
            conn = await asyncio.wait_for(asyncpg.connect(settings.POSTGRES_URL), timeout=15)
            records = await asyncio.wait_for(conn.fetch(query, source.tenant_id), timeout=60)
            
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
            
            logger.info(f"Loaded {len(documents)} documents from database.", event_name="INGEST_POSTGRES_SUCCESS", count=len(documents), table=table_full)
            return documents
        except asyncio.TimeoutError:
            logger.error("PostgreSQL query timed out.", event_name="INGEST_POSTGRES_TIMEOUT")
            return []
        except Exception as e:
            logger.error(f"Database error: {e}", event_name="INGEST_POSTGRES_ERROR", exc_info=True)
            return []
        finally:
            if conn:
                await conn.close()