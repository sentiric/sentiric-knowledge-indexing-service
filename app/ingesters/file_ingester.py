import asyncio
import structlog
from pathlib import Path
from typing import List
from .base import BaseIngester
from app.core.models import Document, DataSource

logger = structlog.get_logger(__name__)

class FileIngester(BaseIngester):
    """
    Yerel dosya sisteminden (container'a mount edilmiş) metin dosyalarını okuyan yükleyici.
    Şimdilik .txt ve .md uzantılarını destekler.
    """

    async def load(self, source: DataSource) -> List[Document]:
        file_path = Path(source.source_uri)
        
        logger.info("Yerel dosya kaynağından veri okunuyor...", path=str(file_path))

        if not file_path.exists():
            logger.error("Dosya bulunamadı.", path=str(file_path))
            return []

        if not file_path.is_file():
            logger.error("Belirtilen yol bir dosya değil.", path=str(file_path))
            return []

        try:
            # Dosya okuma işlemini ana event loop'u bloklamamak için thread'e taşıyoruz
            content = await asyncio.to_thread(self._read_file, file_path)
            
            if not content:
                logger.warning("Dosya boş.", path=str(file_path))
                return []

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
            logger.error("Dosya okunurken hata oluştu.", path=str(file_path), error=str(e))
            return []

    def _read_file(self, path: Path) -> str:
        """Bloklayan IO işlemi."""
        # Sadece text tabanlı dosyaları güvenli okumaya çalışıyoruz
        try:
            return path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            # UTF-8 başarısız olursa fallback (örn: latin-1) denenebilir veya hata fırlatılır
            # Şimdilik loglayıp boş dönüyoruz.
            logger.error("Dosya UTF-8 formatında değil.", path=str(path))
            return ""