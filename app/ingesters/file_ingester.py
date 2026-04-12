# app/ingesters/file_ingester.py
import asyncio
import structlog
from pathlib import Path
from typing import List
from .base import BaseIngester
from app.core.models import Document, DataSource

logger = structlog.get_logger()


class FileIngester(BaseIngester):
    async def load(self, source: DataSource) -> List[Document]:
        file_path = Path(source.source_uri)

        logger.info(f"Reading local file: {file_path}", event_name="INGEST_FILE_FETCH")

        if not file_path.exists():
            logger.error(
                "File not found.",
                event_name="INGEST_FILE_NOT_FOUND",
                path=str(file_path),
            )
            return []

        if not file_path.is_file():
            logger.error(
                "Path is not a file.",
                event_name="INGEST_FILE_INVALID_PATH",
                path=str(file_path),
            )
            return []

        try:
            content = await asyncio.to_thread(self._read_file_safe, file_path)

            if not content:
                logger.warn(
                    "File is empty or unreadable.",
                    event_name="INGEST_FILE_EMPTY",
                    path=str(file_path),
                )
                return []

            logger.info(
                "Successfully read file.",
                event_name="INGEST_FILE_SUCCESS",
                size=len(content),
            )

            return [
                Document(
                    page_content=content,
                    metadata={
                        "source_uri": str(file_path),
                        "source_type": source.source_type,
                        "tenant_id": source.tenant_id,
                        "filename": file_path.name,
                        "extension": file_path.suffix,
                    },
                )
            ]
        except Exception as e:
            logger.error(
                f"Unexpected error processing file: {e}",
                event_name="INGEST_FILE_ERROR",
                exc_info=True,
            )
            return []

    def _read_file_safe(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            logger.warn(
                "UTF-8 decode failed, trying latin-1...",
                event_name="INGEST_FILE_ENCODING_RETRY",
                path=str(path),
            )
            try:
                return path.read_text(encoding="latin-1")
            except Exception:
                return ""
