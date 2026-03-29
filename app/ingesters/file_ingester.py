# app/ingesters/file_ingester.py
import asyncio
import structlog
from pathlib import Path
from typing import List
from .base import BaseIngester
from app.core.models import Document, DataSource

logger = structlog.get_logger(__name__)

class FileIngester(BaseIngester):

    async def load(self, source: DataSource) -> List[Document]:
        file_path = Path(source.source_uri)
        
        log = logger.bind(path=str(file_path), tenant_id=source.tenant_id)
        log.info("Yerel dosya kaynağından veri okunuyor...", event="FILE_INGEST_START")

        if not file_path.exists():
            log.error("Dosya bulunamadı.", event="FILE_NOT_FOUND")
            return []

        if not file_path.is_file():
            log.error("Belirtilen yol bir dosya değil.", event="FILE_PATH_INVALID")
            return []

        try:
            content = await asyncio.to_thread(self._read_file_safe, file_path)
            
            if not content:
                log.warning("Dosya boş veya okunamadı.", event="FILE_EMPTY_OR_UNREADABLE")
                return []

            log.info("Dosya başarıyla okundu.", event="FILE_INGEST_SUCCESS", size=len(content))

            return [
                Document(
                    page_content=content,
                    metadata={
                        "source_uri": str(file_path),
                        "source_type": source.source_type,
                        "tenant_id": source.tenant_id,
                        "filename": file_path.name,
                        "extension": file_path.suffix
                    }
                )
            ]
        except Exception as e:
            log.error("Dosya işlenirken beklenmedik hata.", event="FILE_INGEST_ERROR", error=str(e))
            return []

    def _read_file_safe(self, path: Path) -> str:
        try:
            return path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            logger.warning("UTF-8 decode hatası, latin-1 deneniyor...", event="FILE_DECODE_RETRY", path=str(path))
            try:
                return path.read_text(encoding='latin-1')
            except Exception:
                return ""