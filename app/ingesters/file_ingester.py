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
    Markdown (.md) ve Text (.txt) dosyalarını destekler.
    """

    async def load(self, source: DataSource) -> List[Document]:
        # URI, container içindeki mutlak yol olmalıdır (örn: /opt/sentiric/assets/...)
        file_path = Path(source.source_uri)
        
        log = logger.bind(path=str(file_path), tenant_id=source.tenant_id)
        log.info("Yerel dosya kaynağından veri okunuyor...")

        if not file_path.exists():
            log.error("Dosya bulunamadı.")
            return []

        if not file_path.is_file():
            log.error("Belirtilen yol bir dosya değil.")
            return []

        try:
            # IO işlemini thread'e taşıyarak event loop'u bloklamıyoruz
            content = await asyncio.to_thread(self._read_file_safe, file_path)
            
            if not content:
                log.warning("Dosya boş veya okunamadı.")
                return []

            log.info("Dosya başarıyla okundu.", size=len(content))

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
            log.error("Dosya işlenirken beklenmedik hata.", error=str(e))
            return []

    def _read_file_safe(self, path: Path) -> str:
        """Dosyayı güvenli bir şekilde okur."""
        try:
            return path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            logger.warning("UTF-8 decode hatası, latin-1 deneniyor...", path=str(path))
            try:
                return path.read_text(encoding='latin-1')
            except Exception:
                return ""